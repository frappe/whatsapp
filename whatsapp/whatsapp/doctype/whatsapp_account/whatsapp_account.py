# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WhatsAppAccount(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from whatsapp.whatsapp.doctype.whatsapp_account_append.whatsapp_account_append import (
			WhatsAppAccountAppend,
		)

		access_token: DF.Password | None
		account_name: DF.Data | None
		append_actions: DF.Table[WhatsAppAccountAppend]
		app_id: DF.Data | None
		business_id: DF.Data | None
		phone_id: DF.Data | None
		status: DF.Literal["Active", "Inactive"]
	# end: auto-generated types

	def after_insert(self):
		"""Make the first account the default, so a site with one account never has
		to choose one. Later accounts leave the existing default alone."""
		if not frappe.db.get_single_value("WhatsApp Settings", "default_account"):
			frappe.db.set_single_value("WhatsApp Settings", "default_account", self.name)

	def on_trash(self):
		"""Stop `WhatsApp Settings.default_account` ever naming a deleted account.

		Frappe runs on_trash before its link check (frappe/model/delete_doc.py), so
		clearing the value here is also what lets the last account be deleted at all
		— the Singles link check would otherwise refuse it.
		"""
		if frappe.db.get_single_value("WhatsApp Settings", "default_account") != self.name:
			return

		if frappe.db.count("WhatsApp Account", {"name": ("!=", self.name)}):
			frappe.throw(
				_("{0} is the default WhatsApp account. Set another account as the default before deleting it.").format(
					self.name
				)
			)

		frappe.db.set_single_value("WhatsApp Settings", "default_account", "")
