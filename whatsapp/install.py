# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from whatsapp.whatsapp.api.languages import SUPPORTED_LANGUAGES

WHATSAPP_CHANNEL = "WhatsApp"

SHOW_FOR_WHATSAPP = f"eval:doc.channel=='{WHATSAPP_CHANNEL}'"

CUSTOM_FIELDS = {
	"Notification": [
		{
			"fieldname": "whatsapp_section",
			"fieldtype": "Section Break",
			"label": "WhatsApp",
			"insert_after": "slack_webhook_url",
			"depends_on": SHOW_FOR_WHATSAPP,
		},
		{
			"fieldname": "whatsapp_template",
			"fieldtype": "Link",
			"label": "WhatsApp Template",
			"options": "WhatsApp Template",
			"insert_after": "whatsapp_section",
			"depends_on": SHOW_FOR_WHATSAPP,
			"mandatory_depends_on": SHOW_FOR_WHATSAPP,
		},
		{
			"fieldname": "whatsapp_account",
			"fieldtype": "Link",
			"label": "WhatsApp Account",
			"options": "WhatsApp Account",
			"insert_after": "whatsapp_template",
			"depends_on": SHOW_FOR_WHATSAPP,
			"description": "Leave blank to use the default account from WhatsApp Settings",
		},
	]
}

PROPERTY_SETTERS = (
	("channel", "options"),
	("subject", "depends_on"),
	("subject", "mandatory_depends_on"),
	("message_sb", "depends_on"),
)


def setup_notification_channel() -> None:
	create_custom_fields(CUSTOM_FIELDS, update=True)
	_add_channel_option()
	_show_subject_for_whatsapp()
	_hide_message_for_whatsapp()
	frappe.clear_cache(doctype="Notification")


def seed_languages() -> None:
	"""Rows this doesn't know about are left alone: sync creates codes Meta added after us."""
	stored = dict(frappe.get_all("WhatsApp Language", fields=["name", "language_name"], as_list=True))

	for code, language_name in SUPPORTED_LANGUAGES.items():
		if code not in stored:
			frappe.get_doc(
				doctype="WhatsApp Language", language_code=code, language_name=language_name
			).insert(ignore_permissions=True)
		elif stored[code] != language_name:
			frappe.db.set_value(
				"WhatsApp Language", code, "language_name", language_name, update_modified=False
			)


def teardown_notification_channel() -> None:
	for fieldname, property_name in PROPERTY_SETTERS:
		frappe.db.delete(
			"Property Setter",
			{"doc_type": "Notification", "field_name": fieldname, "property": property_name},
		)

	for field in CUSTOM_FIELDS["Notification"]:
		name = frappe.db.get_value("Custom Field", {"dt": "Notification", "fieldname": field["fieldname"]})
		if name:
			frappe.delete_doc("Custom Field", name, ignore_missing=True)

	frappe.clear_cache(doctype="Notification")


def _add_channel_option() -> None:
	options = _shipped_property("channel", "options")
	if WHATSAPP_CHANNEL in options.split("\n"):
		return

	_set_property("channel", "options", f"{options}\n{WHATSAPP_CHANNEL}", "Small Text")


def _show_subject_for_whatsapp() -> None:
	"""Notification.autoname is `subject or notification_title`, and Subject is hidden for every
	channel but Email and Slack — without this a WhatsApp rule falls back to a hash name."""
	for property_name in ("depends_on", "mandatory_depends_on"):
		expression = _shipped_property("subject", property_name)
		_set_property("subject", property_name, _or_whatsapp(expression), "Code")


def _hide_message_for_whatsapp() -> None:
	expression = _shipped_property("message_sb", "depends_on")
	_set_property("message_sb", "depends_on", _and_not_whatsapp(expression), "Code")


def _shipped_property(fieldname: str, property_name: str) -> str:
	"""Read from DocField rather than Meta: Property Setters never touch it, so a value changed
	upstream flows through on the next migrate instead of being frozen at whatever we appended to."""
	return (
		frappe.db.get_value("DocField", {"parent": "Notification", "fieldname": fieldname}, property_name)
		or ""
	)


def _set_property(fieldname: str, property_name: str, value: str, property_type: str) -> None:
	frappe.make_property_setter(
		{
			"doctype": "Notification",
			"fieldname": fieldname,
			"property": property_name,
			"value": value,
			"property_type": property_type,
		}
	)


def _or_whatsapp(expression: str) -> str:
	return f"eval: ({_strip_eval(expression)}) || doc.channel == '{WHATSAPP_CHANNEL}'"


def _and_not_whatsapp(expression: str) -> str:
	return f"eval: ({_strip_eval(expression)}) && doc.channel != '{WHATSAPP_CHANNEL}'"


def _strip_eval(expression: str) -> str:
	return expression.removeprefix("eval:").strip()
