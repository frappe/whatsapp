# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestWhatsAppAccount(IntegrationTestCase):
	"""
	Integration tests for WhatsAppAccount.
	Use this class for testing interactions between multiple components.
	"""

	def setUp(self):
		# after_insert only claims an empty default, so start from one.
		frappe.db.set_single_value("WhatsApp Settings", "default_account", "")

	def _account(self, suffix):
		# IntegrationTestCase rolls back once per class, not per test, so accounts
		# outlive the test that made them. Namespace them to avoid collisions.
		return frappe.get_doc(
			doctype="WhatsApp Account",
			account_name=f"_Test {self._testMethodName} {suffix}",
			status="Active",
			phone_id=f"1555000{suffix}",
			access_token="test_token",
		).insert()

	def _default(self):
		return frappe.db.get_single_value("WhatsApp Settings", "default_account")

	def test_first_account_becomes_the_default(self):
		account = self._account("A")

		self.assertEqual(self._default(), account.name)

	def test_second_account_leaves_the_default_alone(self):
		first = self._account("A")
		self._account("B")

		self.assertEqual(self._default(), first.name)

	def test_deleting_the_default_is_refused_while_others_remain(self):
		first = self._account("A")
		self._account("B")

		with self.assertRaises(frappe.ValidationError):
			first.delete()

		self.assertEqual(self._default(), first.name)
		self.assertTrue(frappe.db.exists("WhatsApp Account", first.name))

	def test_deleting_a_non_default_leaves_the_default_intact(self):
		first = self._account("A")
		second = self._account("B")

		second.delete()

		self.assertEqual(self._default(), first.name)
		self.assertTrue(frappe.db.exists("WhatsApp Account", first.name))

	def test_deleting_the_last_account_clears_the_default(self):
		# The only test that needs an empty table: on_trash distinguishes "last
		# account" from "one of several". Rolled back with the rest of the class.
		frappe.db.delete("WhatsApp Account")
		account = self._account("A")

		account.delete()

		self.assertFalse(self._default())
		self.assertFalse(frappe.db.exists("WhatsApp Account", account.name))
