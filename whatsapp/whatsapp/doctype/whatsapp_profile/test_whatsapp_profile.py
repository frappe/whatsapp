# Copyright (c) 2026, pratham@frappe.io and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = ["Whatsapp Account"]


class IntegrationTestWhatsappProfile(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")

	def _make_account(self) -> str:
		uid = frappe.generate_hash(length=6)
		doc = frappe.get_doc(
			doctype="Whatsapp Account",
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
			doctype="Whatsapp Profile",
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
			doctype="Whatsapp Profile",
			phone_number="+1234567890",
			whatsapp_account=acc,
			profile_name="John",
		).insert()
		doc2 = frappe.get_doc(
			doctype="Whatsapp Profile",
			phone_number="+1234567890",
			whatsapp_account=acc2,
			profile_name="John (Other)",
		).insert()
		self.assertIsNotNone(doc2.name)

	def test_duplicate_raises(self):
		acc = self._make_account()
		frappe.get_doc(
			doctype="Whatsapp Profile",
			phone_number="+1234567890",
			whatsapp_account=acc,
		).insert()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				doctype="Whatsapp Profile",
				phone_number="+1234567890",
				whatsapp_account=acc,
			).insert()

	def test_get_or_create_profile(self):
		from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import get_or_create_profile

		acc = self._make_account()
		name = get_or_create_profile("+1234567890", acc, "Alice")
		self.assertIsNotNone(name)

		name2 = get_or_create_profile("+1234567890", acc, "Alice Updated")
		self.assertEqual(name2, name)

		profile = frappe.get_doc("Whatsapp Profile", name)
		self.assertEqual(profile.profile_name, "Alice Updated")

	def test_resolve_profile_by_phone(self):
		from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import resolve_profile_by_phone

		acc = self._make_account()
		doc = frappe.get_doc(
			doctype="Whatsapp Profile",
			phone_number="+9999999999",
			whatsapp_account=acc,
		).insert()

		found = resolve_profile_by_phone("+9999999999", acc)
		self.assertEqual(found, doc.name)

		not_found = resolve_profile_by_phone("+0000000000", acc)
		self.assertIsNone(not_found)
