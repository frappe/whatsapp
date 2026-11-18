# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

"""The Flow builder's API: create, save, copy and delete Flows on Meta.

The reads (the Flows list and the builder's document) are in `flows/builder_reads.py`.
"""

import json
import re

import frappe
import requests
from frappe import _
from frappe.utils import get_datetime

from whatsapp.whatsapp.api.utils import log
from whatsapp.whatsapp.doctype.wa_template.wa_template import _get_whatsapp_client
from whatsapp.whatsapp.flows.manage import flow_state, flow_to_write, on_meta
from whatsapp.whatsapp.flows.sync import sync_flow

# From Meta's Flows API reference (POST /{WABA-ID}/flows).
META_CATEGORIES = (
	"SIGN_UP",
	"SIGN_IN",
	"APPOINTMENT_BOOKING",
	"LEAD_GENERATION",
	"CONTACT_US",
	"CUSTOMER_SUPPORT",
	"SURVEY",
	"OTHER",
)

# What `createFlow()` of the builder's model writes; test_authoring checks it against builder/blank.json.
BLANK_FLOW_JSON = {
	"version": "7.3",
	"screens": [
		{
			"id": "WELCOME",
			"title": "Welcome",
			"terminal": True,
			"layout": {
				"type": "SingleColumnLayout",
				"children": [
					{
						"type": "Footer",
						"label": "Continue",
						"on-click-action": {"name": "complete", "payload": {}},
					}
				],
			},
		}
	],
}


class FlowNameError(frappe.ValidationError):
	pass


class FlowCategoriesError(frappe.ValidationError):
	pass


# Unverified: Meta documents no field in its create errors, so the field is guessed from the error text.
META_ERROR_FIELDS = (
	(re.compile(r"\bcategor", re.I), FlowCategoriesError),
	(re.compile(r"\bname\b", re.I), FlowNameError),
)


@frappe.whitelist()
def create_flow(account: str, flow_name: str, categories: list[str], clone_from: str | None = None) -> str:
	"""Create a Draft Flow on Meta, blank or as a copy of `clone_from`, and return its WA Flow name.

	Throws `FlowNameError` or `FlowCategoriesError` for a problem with that field, here or on Meta.
	"""
	frappe.has_permission("WA Flow", "create", throw=True)
	frappe.has_permission("WA Account", "read", doc=account, throw=True)
	if clone_from:
		frappe.has_permission("WA Flow", "read", doc=clone_from, throw=True)
	flow_name = (flow_name or "").strip()
	_validate_name(account, flow_name)
	_validate_categories(categories)
	source = {"clone_flow_id": clone_from} if clone_from else {"flow_json": json.dumps(BLANK_FLOW_JSON)}
	flow_id = _create_on_meta(account, flow_name, categories, source)["id"]
	sync_flow(account, flow_id)
	log(
		"Info",
		"Flow",
		f"Created Flow {flow_name} on Meta" + (f" as a copy of {clone_from}" if clone_from else ""),
		account=account,
		reference_doctype="WA Flow",
		reference_docname=flow_id,
	)
	return flow_id


@frappe.whitelist()
def copy_flow(name: str, flow_name: str) -> str:
	"""Make a copy: a new Draft cloned on Meta from any Flow, published or not."""
	source = frappe.get_doc("WA Flow", name)
	source.check_permission("read")
	return create_flow(
		source.whatsapp_account, flow_name, split_categories(source.categories), clone_from=name
	)


@frappe.whitelist()
def save_flow(name: str, flow_json: str, modified: str) -> dict:
	"""Store and upload the Flow JSON of a Draft, and return `flow_state`.

	Meta's validation errors are part of the result, not an error: the JSON is saved with them.
	Throws `frappe.TimestampMismatchError` when the Flow changed after `modified` (from the builder's read).
	"""
	flow = frappe.get_doc("WA Flow", name, for_update=True)
	flow.check_permission("write")
	_require_draft(flow, _("Only a Draft Flow can be saved. This one is {0}."))
	if get_datetime(modified) != flow.modified:
		frappe.throw(
			_("This Flow changed since you opened it. Reload it to see the changes, then make yours again."),
			frappe.TimestampMismatchError,
		)
	flow.flow_json = flow_json
	flow.save()
	return flow_state(flow)


@frappe.whitelist()
def delete_flow(name: str) -> None:
	"""Delete a Draft on Meta, then here. Refused while a template has a Flow button on it."""
	flow = flow_to_write(name)
	_require_draft(flow, _("Only a Draft Flow can be deleted. This one is {0}."))
	if templates := templates_using(name):
		frappe.throw(
			_("Flow {0} is used by these templates: {1}. Remove its Flow button from them first.").format(
				flow.flow_name, ", ".join(template.template_label for template in templates)
			)
		)
	client = _get_whatsapp_client(flow.whatsapp_account)
	on_meta(flow, _("Could not delete the Flow"), lambda: client.delete_flow(flow.flow_id))
	frappe.delete_doc("WA Flow", flow.name, ignore_permissions=True)
	log(
		"Info",
		"Flow",
		f"Deleted Flow {flow.flow_name} ({flow.flow_id}) on Meta",
		account=flow.whatsapp_account,
	)


def templates_using(flow: str) -> list[dict]:
	"""The WA Templates with a Flow button on `flow`, with their Flow button rows, by label."""
	buttons = frappe.get_all(
		"WA Template Button",
		filters={"parenttype": "WA Template", "button_type": "Flow", "flow": flow},
		fields=["parent", "flow_inputs", "flow_response_actions"],
		order_by="idx",
	)
	labels = dict(
		frappe.get_all(
			"WA Template",
			filters={"name": ("in", {button.parent for button in buttons})},
			fields=["name", "template_label"],
			as_list=True,
		)
	)
	templates = {}
	for button in buttons:
		template = templates.setdefault(
			button.parent, frappe._dict(name=button.parent, template_label=labels[button.parent], buttons=[])
		)
		template.buttons.append(button)
	return sorted(templates.values(), key=lambda template: template.template_label)


def split_categories(categories: str | None) -> list[str]:
	return [category.strip() for category in (categories or "").split(",") if category.strip()]


def _validate_name(account: str, flow_name: str) -> None:
	if not flow_name:
		frappe.throw(_("Give the Flow a name"), FlowNameError)
	business_id = frappe.db.get_value("WA Account", account, "business_id")
	if frappe.db.exists("WA Flow", {"business_id": business_id, "flow_name": flow_name}):
		frappe.throw(
			_("A Flow named {0} already exists in this WhatsApp Business Account").format(flow_name),
			FlowNameError,
		)


def _validate_categories(categories: list[str]) -> None:
	if not categories:
		frappe.throw(_("Choose at least one category"), FlowCategoriesError)
	if unknown := [category for category in categories if category not in META_CATEGORIES]:
		frappe.throw(
			_("{0} is not a Flow category. Use: {1}").format(", ".join(unknown), ", ".join(META_CATEGORIES)),
			FlowCategoriesError,
		)


def _require_draft(flow, refusal: str) -> None:
	if flow.status != "Draft":
		frappe.throw(refusal.format(_(flow.status)))


def _create_on_meta(account: str, flow_name: str, categories: list[str], source: dict) -> dict:
	try:
		return _get_whatsapp_client(account).create_flow(flow_name, categories, **source)
	except requests.RequestException as e:
		log("Error", "Flow", f"Could not create Flow {flow_name} on Meta: {e}", account=account)
		frappe.throw(_("Could not create the Flow: {0}").format(e), _field_error(str(e)))


def _field_error(meta_message: str) -> type[frappe.ValidationError]:
	return next(
		(error for pattern, error in META_ERROR_FIELDS if pattern.search(meta_message)),
		frappe.ValidationError,
	)
