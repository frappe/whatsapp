# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import datetime
import re

import frappe
import phonenumbers
from frappe import _
from frappe.geo.country_info import get_country_info
from frappe.model.document import Document
from phonenumbers import NumberParseException, PhoneNumberFormat

FALLBACK_REGION = "IN"


class WAProfile(Document):
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
		return frappe.db.count("WA Message", {"to": self.name})

	@property
	def last_message_at(self) -> datetime.datetime | None:
		if not self.name:
			return None
		# Latest activity across both directions: take the most recently created
		# message and prefer its WhatsApp-provided timestamp, falling back to the
		# record's creation time when the timestamp is absent (e.g. outbound).
		rows = frappe.get_all(
			"WA Message",
			filters={"to": self.name},
			fields=["timestamp", "creation"],
			order_by="creation desc",
			limit=1,
		)
		if not rows:
			return None
		return rows[0].timestamp or rows[0].creation

	def validate(self) -> None:
		self.phone_number = normalize_phone(self.phone_number)
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
		if frappe.db.exists("WA Profile", filters):
			frappe.throw(
				_("WhatsApp Profile for phone {0} under account {1} already exists").format(
					self.phone_number, self.whatsapp_account
				)
			)

	def _set_defaults(self) -> None:
		if not self.status:
			self.status = "Active"


def get_default_region() -> str:
	"""Region that numbers typed without a country code are parsed in."""
	country = frappe.db.get_single_value("System Settings", "country")
	if not country:
		return FALLBACK_REGION
	code = get_country_info(country).get("code")
	return code.upper() if code else FALLBACK_REGION


def normalize_phone(phone_number: str | None) -> str:
	"""E.164 form of a phone number. One that does not parse as valid keeps its digits
	behind a plus sign, which is still stable across spacing and punctuation."""
	if not phone_number:
		return ""
	raw = phone_number.strip()
	digits = re.sub(r"\D", "", raw)
	if not digits:
		return ""

	region = get_default_region()
	for candidate in (raw, f"+{digits}"):
		try:
			parsed = phonenumbers.parse(candidate, region)
		except NumberParseException:
			continue
		if phonenumbers.is_valid_number(parsed):
			return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
	return f"+{digits}"


def get_or_create_profile(
	phone_number: str,
	account_name: str,
	profile_name: str | None = None,
	wa_id: str | None = None,
) -> str:
	phone_number = normalize_phone(phone_number)
	existing = resolve_profile_by_phone(phone_number, account_name)
	if existing:
		profile = frappe.get_doc("WA Profile", existing)
		if profile_name and profile.profile_name != profile_name:
			profile.db_set("profile_name", profile_name)
		return profile.name

	doc = frappe.new_doc("WA Profile")
	doc.phone_number = phone_number
	doc.whatsapp_account = account_name
	doc.profile_name = profile_name or phone_number
	doc.wa_id = wa_id or phone_number
	doc.status = "Active"
	doc.flags.ignore_permissions = True

	# A concurrent delivery can insert the same sender first: the unique index then
	# rejects this insert, and only a locking read sees the profile it committed.
	frappe.db.savepoint("whatsapp_profile_insert")
	try:
		doc.insert()
	except frappe.ValidationError, frappe.DuplicateEntryError:
		frappe.db.rollback(save_point="whatsapp_profile_insert")
		existing = resolve_profile_by_phone(phone_number, account_name, for_update=True)
		if not existing:
			raise
		return existing
	return doc.name


def resolve_profile_by_phone(phone_number: str, account_name: str, for_update: bool = False) -> str | None:
	return frappe.db.get_value(
		"WA Profile",
		{"phone_number": normalize_phone(phone_number), "whatsapp_account": account_name},
		"name",
		for_update=for_update,
	)


def lock_profile(profile_name: str) -> None:
	"""Hold the profile's row until this transaction ends, so concurrent messages from
	one sender are handled one at a time."""
	frappe.db.get_value("WA Profile", profile_name, "name", for_update=True)


def ensure_unique_phone_per_account() -> None:
	"""The controller check cannot stop two concurrent inserts of the same number."""
	frappe.db.add_unique("WA Profile", ["whatsapp_account", "phone_number"])
