import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.patches.v1_0.rename_profiles_to_hash_names import execute
from whatsapp.whatsapp.api.utils import log


class IntegrationTestRenameProfilesToHashNames(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		uid = frappe.generate_hash(length=6)
		self.account = (
			frappe.get_doc(
				doctype="WhatsApp Account",
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

	def _legacy_profile(self, display_name: str) -> str:
		"""A profile as the old `field:profile_name` autoname stored it."""
		hashed = (
			frappe.get_doc(
				doctype="WhatsApp Profile",
				phone_number=f"+1415555{frappe.generate_hash(length=4)}",
				whatsapp_account=self.account,
				profile_name=display_name,
			)
			.insert()
			.name
		)
		frappe.rename_doc("WhatsApp Profile", hashed, display_name, force=True, show_alert=False)
		return display_name

	def test_legacy_profile_takes_a_hash_name_and_keeps_its_records(self):
		display_name = f"Legacy Sender {frappe.generate_hash(length=6)}"
		self._legacy_profile(display_name)
		message = frappe.get_doc(
			doctype="WhatsApp Message",
			direction="Incoming",
			to=display_name,
			whatsapp_account=self.account,
			message="hello",
			status="Sent",
			message_id=f"wamid_{frappe.generate_hash(length=8)}",
		)
		message.flags.ignore_permissions = True
		message = message.insert().name
		log_entry = log(
			"Info",
			"Message",
			"legacy reference",
			reference_doctype="WhatsApp Profile",
			reference_docname=display_name,
		)

		execute()

		renamed = frappe.get_all(
			"WhatsApp Profile",
			filters={"whatsapp_account": self.account},
			fields=["name", "profile_name"],
		)
		self.assertEqual(len(renamed), 1)
		self.assertNotEqual(renamed[0].name, display_name)
		self.assertEqual(renamed[0].profile_name, display_name)
		self.assertEqual(frappe.db.get_value("WhatsApp Message", message, "to"), renamed[0].name)
		self.assertEqual(frappe.db.get_value("WhatsApp Log", log_entry, "reference_docname"), renamed[0].name)
