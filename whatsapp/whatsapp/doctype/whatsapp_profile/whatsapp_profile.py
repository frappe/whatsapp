# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

import datetime

import frappe
from frappe import _
from frappe.model.document import Document


class WhatsAppProfile(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.dynamic_link.dynamic_link import DynamicLink
		from frappe.types import DF

		last_message_at: DF.Datetime | None
		links: DF.Table[DynamicLink]
		phone_number: DF.Data
		profile_name: DF.Data | None
		status: DF.Literal["Active", "Blocked", "Archived"]
		wa_id: DF.Data | None
		whatsapp_account: DF.Link
	# end: auto-generated types

	@property
	def message_count(self) -> int:
		if not self.name:
			return 0
		return frappe.db.count("WhatsApp Message", {"to": self.name})

	@property
	def last_message_at(self) -> datetime.datetime | None:
		if not self.name:
			return None
		# Latest activity across both directions: take the most recently created
		# message and prefer its WhatsApp-provided timestamp, falling back to the
		# record's creation time when the timestamp is absent (e.g. outbound).
		rows = frappe.get_all(
			"WhatsApp Message",
			filters={"to": self.name},
			fields=["timestamp", "creation"],
			order_by="creation desc",
			limit=1,
		)
		if not rows:
			return None
		return rows[0].timestamp or rows[0].creation

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
		if frappe.db.exists("WhatsApp Profile", filters):
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
		profile = frappe.get_doc("WhatsApp Profile", existing)
		if profile_name and profile.profile_name != profile_name:
			profile.db_set("profile_name", profile_name)
		return profile.name

	doc = frappe.new_doc("WhatsApp Profile")
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
		"WhatsApp Profile",
		{"phone_number": phone_number, "whatsapp_account": account_name},
		"name",
	)
