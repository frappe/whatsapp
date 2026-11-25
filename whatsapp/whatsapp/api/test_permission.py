import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.api.permission import has_app_permission


class TestHasAppPermission(IntegrationTestCase):
	def test_system_manager_can_open_app(self):
		frappe.set_user("Administrator")
		self.assertTrue(has_app_permission())

	def test_user_without_settings_access_cannot_open_app(self):
		frappe.set_user("Guest")
		self.assertFalse(has_app_permission())

	def tearDown(self):
		frappe.set_user("Administrator")
