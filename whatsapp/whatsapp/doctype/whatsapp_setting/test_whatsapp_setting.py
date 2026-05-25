# Copyright (c) 2026, pratham@frappe.io and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestWhatsappSetting(IntegrationTestCase):
	"""
	Integration tests for WhatsappSetting.
	Use this class for testing interactions between multiple components.
	"""

	def test_default_account_auto_populates_on_outgoing_message(self):
		account = frappe.get_doc(
			doctype="Whatsapp Account",
			account_name="_Test Default Account",
			status="Active",
			phone_id="15550001111",
			access_token="test_token",
		).insert()
		frappe.db.set_single_value("Whatsapp Setting", "default_account", account.name)

		msg = frappe.get_doc(
			doctype="Whatsapp Message",
			to="+15551234567",
			direction="Outgoing",
		)
		msg.insert()

		self.assertEqual(msg.whatsapp_account, account.name)
