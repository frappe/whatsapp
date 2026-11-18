import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.patches.v1_0.grant_flow_response_read import execute

LEVEL_ONE_READ = {"parent": "WA Message", "role": "System Manager", "permlevel": 1}


class IntegrationTestGrantFlowResponseRead(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")

	def test_custom_permissions_gain_the_level_one_read(self):
		frappe.permissions.setup_custom_perms("WA Message")
		frappe.db.delete("Custom DocPerm", LEVEL_ONE_READ)

		execute()

		self.assertEqual(frappe.db.get_value("Custom DocPerm", LEVEL_ONE_READ, "read"), 1)

	def test_standard_permissions_are_left_alone(self):
		frappe.db.delete("Custom DocPerm", {"parent": "WA Message"})

		execute()

		self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": "WA Message"}))
