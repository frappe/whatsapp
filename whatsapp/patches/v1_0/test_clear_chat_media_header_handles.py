import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.patches.v1_0.clear_chat_media_header_handles import execute
from whatsapp.whatsapp.doctype.wa_template.wa_template import _ensure_language


class IntegrationTestClearChatMediaHeaderHandles(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		_ensure_language("en_US")
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

	def _template(self, **fields) -> str:
		uid = frappe.generate_hash(length=6)
		return (
			frappe.get_doc(
				doctype="WA Template",
				template_label=f"_Test Patch Template {uid}",
				template_name=f"_test_patch_template_{uid}",
				template_type="Utility",
				language="en_US",
				message="Body",
				header_type="Image",
				whatsapp_account=self.account,
				whatsapp_template_id=uid,
				**fields,
			)
			.insert()
			.name
		)

	def test_clears_handle_of_local_sample(self):
		name = self._template(header_media="/files/sample.png", header_media_handle="chat_media_id")

		execute()

		self.assertFalse(frappe.db.get_value("WA Template", name, "header_media_handle"))

	def test_keeps_handle_synced_from_meta(self):
		name = self._template(header_media_handle="https://scontent.whatsapp.net/sample")

		execute()

		self.assertEqual(
			frappe.db.get_value("WA Template", name, "header_media_handle"),
			"https://scontent.whatsapp.net/sample",
		)
