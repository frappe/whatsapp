from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.patches.v1_0.normalize_profile_phone_numbers import execute


class IntegrationTestNormalizeProfilePhoneNumbers(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		uid = frappe.generate_hash(length=6)
		self.account = (
			frappe.get_doc(
				doctype="WA Account",
				account_name=f"_Test Patch Account {uid}",
				status="Active",
				phone_id=f"phone_{uid}",
				business_id="test_business",
				app_id="test_app",
				access_token="test_token",
			)
			.insert()
			.name
		)
		region = patch(
			"whatsapp.whatsapp.doctype.wa_profile.wa_profile.get_default_region",
			return_value="IN",
		)
		region.start()
		self.addCleanup(region.stop)

	def _stored_profile(self, phone_number: str, creation: str, wa_id: str | None = None) -> str:
		"""A profile as it sat in the database before numbers were normalized on save."""
		placeholder = f"+1415555{frappe.generate_hash(length=4)}"
		name = (
			frappe.get_doc(
				doctype="WA Profile",
				phone_number=placeholder,
				whatsapp_account=self.account,
				profile_name=phone_number,
			)
			.insert()
			.name
		)
		frappe.db.set_value(
			"WA Profile",
			name,
			{"phone_number": phone_number, "wa_id": wa_id, "creation": creation},
			update_modified=False,
		)
		return name

	def _profiles(self) -> list:
		return frappe.get_all(
			"WA Profile", filters={"whatsapp_account": self.account}, fields=["name", "phone_number"]
		)

	def _message_to(self, profile: str) -> str:
		doc = frappe.get_doc(
			doctype="WA Message",
			direction="Incoming",
			to=profile,
			whatsapp_account=self.account,
			message="hello",
			status="Sent",
			message_id=f"wamid_{frappe.generate_hash(length=8)}",
		)
		doc.flags.ignore_permissions = True
		return doc.insert().name

	def test_meta_profile_absorbs_a_later_e164_duplicate(self):
		meta = self._stored_profile("919876500001", "2020-01-01 00:00:00", wa_id="919876500001")
		host = self._stored_profile("+919876500001", "2020-01-02 00:00:00", wa_id="+919876500001")
		message = self._message_to(host)
		todo = frappe.get_doc(doctype="ToDo", description="linked record").insert().name
		host_doc = frappe.get_doc("WA Profile", host)
		host_doc.append("links", {"link_doctype": "ToDo", "link_name": todo, "link_title": todo})
		host_doc.db_update_all()

		execute()

		self.assertEqual(self._profiles(), [{"name": meta, "phone_number": "+919876500001"}])
		self.assertEqual(frappe.db.get_value("WA Message", message, "to"), meta)
		links = frappe.get_doc("WA Profile", meta).links
		self.assertEqual([(link.link_doctype, link.link_name) for link in links], [("ToDo", todo)])

	def test_profile_with_a_wa_id_survives_an_older_one_without(self):
		self._stored_profile("+91 98765 00002", "2020-01-01 00:00:00")
		meta = self._stored_profile("919876500002", "2020-01-02 00:00:00", wa_id="919876500002")

		execute()

		self.assertEqual(self._profiles(), [{"name": meta, "phone_number": "+919876500002"}])

	def test_three_spellings_of_one_number_merge_into_one_profile(self):
		self._stored_profile("+91 98765 00003", "2020-01-01 00:00:00")
		meta = self._stored_profile("919876500003", "2020-01-02 00:00:00", wa_id="919876500003")
		self._stored_profile("+919876500003", "2020-01-03 00:00:00")

		execute()

		self.assertEqual(self._profiles(), [{"name": meta, "phone_number": "+919876500003"}])

	def test_stored_digits_keep_their_country_code(self):
		singapore = self._stored_profile("6591234567", "2020-01-01 00:00:00", wa_id="6591234567")

		execute()

		self.assertEqual(frappe.db.get_value("WA Profile", singapore, "phone_number"), "+6591234567")
