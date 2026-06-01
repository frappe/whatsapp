# Copyright (c) 2026, pratham@frappe.io and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = ["WhatsApp Account"]


class IntegrationTestWhatsAppProfile(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")

	def _make_account(self) -> str:
		uid = frappe.generate_hash(length=6)
		doc = frappe.get_doc(
			doctype="WhatsApp Account",
			account_name=f"_Test Account {uid}",
			status="Active",
			phone_id="1234567890",
			business_id="test_business",
			app_id="test_app",
			access_token="test_token",
		).insert()
		return doc.name

	def test_create_profile(self):
		acc = self._make_account()
		doc = frappe.get_doc(
			doctype="WhatsApp Profile",
			phone_number="+1234567890",
			whatsapp_account=acc,
			profile_name="John Doe",
		).insert()
		self.assertEqual(doc.phone_number, "+1234567890")
		self.assertEqual(doc.profile_name, "John Doe")
		self.assertEqual(doc.status, "Active")

	def test_unique_per_account(self):
		acc = self._make_account()
		acc2 = self._make_account()
		frappe.get_doc(
			doctype="WhatsApp Profile",
			phone_number="+1234567890",
			whatsapp_account=acc,
			profile_name="John",
		).insert()
		doc2 = frappe.get_doc(
			doctype="WhatsApp Profile",
			phone_number="+1234567890",
			whatsapp_account=acc2,
			profile_name="John (Other)",
		).insert()
		self.assertIsNotNone(doc2.name)

	def test_duplicate_raises(self):
		acc = self._make_account()
		frappe.get_doc(
			doctype="WhatsApp Profile",
			phone_number="+1234567890",
			whatsapp_account=acc,
			profile_name="Duplicate Test",
		).insert()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				doctype="WhatsApp Profile",
				phone_number="+1234567890",
				whatsapp_account=acc,
				profile_name="Duplicate Test 2",
			).insert()

	def test_get_or_create_profile(self):
		from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import get_or_create_profile

		acc = self._make_account()
		name = get_or_create_profile("+1234567890", acc, "Alice")
		self.assertIsNotNone(name)

		name2 = get_or_create_profile("+1234567890", acc, "Alice Updated")
		self.assertEqual(name2, name)

		profile = frappe.get_doc("WhatsApp Profile", name)
		self.assertEqual(profile.profile_name, "Alice Updated")

	def test_virtual_message_fields(self):
		import datetime

		acc = self._make_account()
		profile = frappe.get_doc(
			doctype="WhatsApp Profile",
			phone_number="+1555000111",
			whatsapp_account=acc,
			profile_name="Virtual Fields",
		).insert()

		# No messages yet: count is zero and last activity is unknown.
		fresh = frappe.get_doc("WhatsApp Profile", profile.name)
		self.assertEqual(fresh.message_count, 0)
		self.assertIsNone(fresh.last_message_at)

		def _msg(direction, ts=None):
			frappe.get_doc(
				doctype="WhatsApp Message",
				to=profile.name,
				direction=direction,
				whatsapp_account=acc,
				message="hi",
				timestamp=ts,
			).insert()

		_msg("Incoming", datetime.datetime(2026, 5, 1, 10, 0, 0))
		_msg("Outgoing", datetime.datetime(2026, 5, 30, 15, 30, 0))
		_msg("Incoming")  # no explicit timestamp -> falls back to creation

		reloaded = frappe.get_doc("WhatsApp Profile", profile.name)
		# Counts both directions.
		self.assertEqual(reloaded.message_count, 3)
		# Latest message has no timestamp, so last_message_at falls back to its creation.
		self.assertIsNotNone(reloaded.last_message_at)
		# Virtual fields must serialize (this is the path the form/getdoc uses).
		as_dict = reloaded.as_dict()
		self.assertEqual(as_dict["message_count"], 3)
		self.assertEqual(as_dict["last_message_at"], reloaded.last_message_at)

	def test_resolve_profile_by_phone(self):
		from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import resolve_profile_by_phone

		acc = self._make_account()
		doc = frappe.get_doc(
			doctype="WhatsApp Profile",
			phone_number="+9999999999",
			whatsapp_account=acc,
			profile_name="+9999999999",
		).insert()

		found = resolve_profile_by_phone("+9999999999", acc)
		self.assertEqual(found, doc.name)

		not_found = resolve_profile_by_phone("+0000000000", acc)
		self.assertIsNone(not_found)
