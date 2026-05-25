# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class WhatsappProfile(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.dynamic_link.dynamic_link import DynamicLink
		from frappe.types import DF

		last_message_at: DF.Datetime | None
		links: DF.Table[DynamicLink]
		message_count: DF.Int
		phone_number: DF.Data
		profile_name: DF.Data | None
		status: DF.Literal["Active", "Blocked", "Archived"]
		wa_id: DF.Data | None
		whatsapp_account: DF.Link
	# end: auto-generated types

	def validate(self) -> None:
		self._validate_unique_phone_per_account()

	def before_insert(self) -> None:
		self._set_defaults()

	def _validate_unique_phone_per_account(self) -> None:
		if not self.phone_number or not self.whatsapp_account:
			return
		filters = {
			"phone_number": self.phone_number,
			"whatsapp_account": self.whatsapp_account,
		}
		if self.name:
			filters["name"] = ["!=", self.name]
		if frappe.db.exists("Whatsapp Profile", filters):
			frappe.throw(
				_("WhatsApp Profile for phone {0} under account {1} already exists").format(
					self.phone_number, self.whatsapp_account
				)
			)

	def _set_defaults(self) -> None:
		if not self.status:
			self.status = "Active"
		if self.phone_number:
			self.phone_number = self.phone_number.strip()


def get_or_create_profile(
	phone_number: str,
	account_name: str,
	profile_name: str | None = None,
	wa_id: str | None = None,
) -> str:
	existing = resolve_profile_by_phone(phone_number, account_name)
	if existing:
		profile = frappe.get_doc("Whatsapp Profile", existing)
		if profile_name and profile.profile_name != profile_name:
			profile.db_set("profile_name", profile_name)
		return profile.name

	doc = frappe.new_doc("Whatsapp Profile")
	doc.phone_number = phone_number
	doc.whatsapp_account = account_name
	doc.profile_name = profile_name or phone_number
	doc.wa_id = wa_id or phone_number
	doc.status = "Active"
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def resolve_profile_by_phone(phone_number: str, account_name: str) -> str | None:
	return frappe.db.get_value(
		"Whatsapp Profile",
		{"phone_number": phone_number, "whatsapp_account": account_name},
		"name",
	)


def update_profile_activity(profile_name: str) -> None:
	profile = frappe.get_doc("Whatsapp Profile", profile_name)
	profile.db_set("last_message_at", now_datetime())
	profile.db_set("message_count", (profile.message_count or 0) + 1)
