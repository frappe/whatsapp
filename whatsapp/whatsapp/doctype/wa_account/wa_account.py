# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe import _
from frappe.model.document import Document

from whatsapp.whatsapp.doctype.wa_message.wa_message import _get_whatsapp_client

# Which fieldtypes can hold the value an append action writes into each mapping slot.
# Drives both the pickers in the grid and the check on save.
APPEND_FIELD_TYPES = {
	"message_field": ("Data", "Small Text", "Text", "Long Text", "Text Editor"),
	"sender_field": ("Data", "Phone", "Small Text", "Text"),
	"sender_name_field": ("Data", "Small Text", "Text"),
	"timestamp_field": ("Date", "Datetime"),
}


class WAAccount(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from whatsapp.whatsapp.doctype.wa_account_append.wa_account_append import (
			WAAccountAppend,
		)

		access_token: DF.Password | None
		account_name: DF.Data | None
		append_actions: DF.Table[WAAccountAppend]
		app_id: DF.Data | None
		business_id: DF.Data | None
		phone_id: DF.Data | None
		status: DF.Literal["Active", "Inactive"]
	# end: auto-generated types

	def validate(self):
		self.validate_append_actions()

	def validate_append_actions(self):
		"""Check every mapped fieldname against the doctype the action appends to.

		`Document.set` accepts a name no field has and drops it on insert, so a stale or
		mistyped mapping would otherwise create documents with the value missing and
		nothing to say why. A child table or single target fails later instead, once per
		message, into the log.
		"""
		for action in self.append_actions:
			target_meta = frappe.get_meta(action.append_to)
			if target_meta.istable or target_meta.issingle:
				frappe.throw(
					_("Row #{0}: cannot append to {1}; a child table or single has no list to add to").format(
						action.idx, action.append_to
					)
				)
			for slot in APPEND_FIELD_TYPES:
				_validate_mapped_field(action, slot, target_meta)

	def after_insert(self):
		"""Make the first account the default, so a site with one account never has
		to choose one. Later accounts leave the existing default alone."""
		if not frappe.db.get_single_value("WA Settings", "default_account"):
			frappe.db.set_single_value("WA Settings", "default_account", self.name)

	def on_trash(self):
		"""Stop `WhatsApp Settings.default_account` ever naming a deleted account.

		Frappe runs on_trash before its link check (frappe/model/delete_doc.py), so
		clearing the value here is also what lets the last account be deleted at all
		— the Singles link check would otherwise refuse it.
		"""
		if frappe.db.get_single_value("WA Settings", "default_account") != self.name:
			return

		if frappe.db.count("WA Account", {"name": ("!=", self.name)}):
			frappe.throw(
				_(
					"{0} is the default WhatsApp account. Set another account as the default before deleting it."
				).format(self.name)
			)

		frappe.db.set_single_value("WA Settings", "default_account", "")


def _validate_mapped_field(action, slot: str, target_meta) -> None:
	"""Throw unless the field mapped into `slot` exists on the target and can hold the value."""
	fieldname = action.get(slot)
	if not fieldname:
		return

	label = _(frappe.get_meta(action.doctype).get_label(slot))
	df = target_meta.get_field(fieldname)

	if not df:
		frappe.throw(
			_("Row #{0}: {1} '{2}' does not exist on {3}").format(
				action.idx, label, fieldname, action.append_to
			)
		)

	fieldtypes = APPEND_FIELD_TYPES[slot]
	if df.fieldtype not in fieldtypes:
		frappe.throw(
			_("Row #{0}: {1} '{2}' is a {3} field; {1} must be one of {4}").format(
				action.idx, label, fieldname, df.fieldtype, ", ".join(fieldtypes)
			)
		)


@frappe.whitelist()
def get_append_field_options(target_doctype: str = "", slot: str = "", txt: str = "") -> list[dict]:
	"""Fields on `target_doctype` an append action can write its `slot` value into.

	Feeds the autocomplete on each append action row, so the options are those of the
	doctype that row appends to, not of every row's doctype.
	"""
	frappe.has_permission("WA Account", "write", throw=True)

	if not target_doctype or slot not in APPEND_FIELD_TYPES:
		return []

	frappe.has_permission(target_doctype, "read", throw=True)

	fieldtypes = APPEND_FIELD_TYPES[slot]
	txt = (txt or "").lower()

	return [
		{
			"value": df.fieldname,
			"label": df.fieldname,
			"description": f"{_(df.label)} ({df.fieldtype})" if df.label else df.fieldtype,
		}
		for df in frappe.get_meta(target_doctype).fields
		if df.fieldtype in fieldtypes and (txt in df.fieldname.lower() or txt in (df.label or "").lower())
	]


@frappe.whitelist()
def check_webhook_subscription(account: str) -> dict:
	"""Ask Meta which apps are subscribed to this account's WABA.

	Webhook events only arrive for a WABA that has the app subscribed, which the
	dashboard's webhook verification step does not do by itself.
	"""
	frappe.has_permission("WA Account", "write", throw=True)
	account_doc = frappe.get_doc("WA Account", account)
	if not account_doc.business_id:
		frappe.throw(_("Set the Business ID (WABA ID) before checking the subscription"))

	try:
		response = _client_for(account_doc).get_subscribed_apps()
	except requests.HTTPError as e:
		frappe.throw(_("Meta rejected the request: {0}").format(e))

	apps = [entry.get("whatsapp_business_api_data", {}) for entry in response.get("data", [])]
	app_ids = {app.get("id") for app in apps}
	return {
		"subscribed_apps": apps,
		"subscribed": account_doc.app_id in app_ids if account_doc.app_id else bool(app_ids),
	}


@frappe.whitelist()
def subscribe_webhook(account: str) -> dict:
	"""Subscribe the app behind the access token to this account's WABA, then re-check."""
	frappe.has_permission("WA Account", "write", throw=True)
	account_doc = frappe.get_doc("WA Account", account)
	if not account_doc.business_id:
		frappe.throw(_("Set the Business ID (WABA ID) before subscribing"))

	try:
		_client_for(account_doc).subscribe_app()
	except requests.HTTPError as e:
		frappe.throw(_("Meta rejected the subscription: {0}").format(e))

	return check_webhook_subscription(account)


def _client_for(account_doc):
	return _get_whatsapp_client(account_doc, frappe.get_single("WA Settings"))
