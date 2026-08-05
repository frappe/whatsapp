# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import secrets

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import get_or_create_profile


class IntegrationTestWhatsAppSetting(IntegrationTestCase):
	"""
	Integration tests for WhatsAppSettings.
	Use this class for testing interactions between multiple components.
	"""

	def test_default_account_auto_populates_on_outgoing_message(self):
		account = frappe.get_doc(
			doctype="WhatsApp Account",
			account_name="_Test Default Account",
			status="Active",
			phone_id="15550001111",
			access_token="test_token",
		).insert()
		frappe.db.set_single_value("WhatsApp Settings", "default_account", account.name)

		phone = f"+1{secrets.randbelow(10**10):010d}"
		get_or_create_profile(phone, account.name, phone)
		msg = frappe.get_doc(
			doctype="WhatsApp Message",
			to=phone,
			direction="Outgoing",
		)
		msg.insert()

		self.assertEqual(msg.whatsapp_account, account.name)
