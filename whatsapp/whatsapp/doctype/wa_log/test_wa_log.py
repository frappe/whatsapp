# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.api.utils import log

SYSTEM_MANAGER = "_test_wa_log_manager@example.com"


class IntegrationTestWALog(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("User", SYSTEM_MANAGER):
			frappe.get_doc(
				doctype="User", email=SYSTEM_MANAGER, first_name="WA Log Manager", send_welcome_email=0
			).insert().add_roles("System Manager")

	def test_no_one_can_create_or_edit_a_log(self):
		name = log("Info", "System", "from code")

		with self.set_user(SYSTEM_MANAGER):
			self.assertTrue(frappe.has_permission("WA Log", "read", name))
			for ptype in ("create", "write"):
				with self.subTest(ptype=ptype):
					self.assertFalse(frappe.has_permission("WA Log", ptype, name))

			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc(doctype="WA Log", level="Info", message="by hand").insert()

	def test_code_writes_logs_without_permission(self):
		with self.set_user(SYSTEM_MANAGER):
			name = log("Info", "System", "from code")

		self.assertEqual(frappe.db.get_value("WA Log", name, "message"), "from code")
