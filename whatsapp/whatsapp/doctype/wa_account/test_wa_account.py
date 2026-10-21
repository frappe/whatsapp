# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from unittest.mock import patch

import frappe
import requests
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.doctype.wa_account.wa_account import (
	check_webhook_subscription,
	get_append_field_options,
	subscribe_webhook,
)

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestWAAccount(IntegrationTestCase):
	"""
	Integration tests for WAAccount.
	Use this class for testing interactions between multiple components.
	"""

	def setUp(self):
		# after_insert only claims an empty default, so start from one.
		frappe.db.set_single_value("WA Settings", "default_account", "")

	def _account(self, suffix):
		# IntegrationTestCase rolls back once per class, not per test, so accounts
		# outlive the test that made them. Namespace them to avoid collisions.
		return frappe.get_doc(
			doctype="WA Account",
			account_name=f"_Test {self._testMethodName} {suffix}",
			status="Active",
			phone_id=f"1555000{suffix}",
			access_token="test_token",
		).insert()

	def _default(self):
		return frappe.db.get_single_value("WA Settings", "default_account")

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
		self.assertTrue(frappe.db.exists("WA Account", first.name))

	def test_deleting_a_non_default_leaves_the_default_intact(self):
		first = self._account("A")
		second = self._account("B")

		second.delete()

		self.assertEqual(self._default(), first.name)
		self.assertTrue(frappe.db.exists("WA Account", first.name))

	def test_deleting_the_last_account_clears_the_default(self):
		# The only test that needs an empty table: on_trash distinguishes "last
		# account" from "one of several". Rolled back with the rest of the class.
		frappe.db.delete("WA Account")
		account = self._account("A")

		account.delete()

		self.assertFalse(self._default())
		self.assertFalse(frappe.db.exists("WA Account", account.name))

	def _append_action(self, account, **mapping):
		account.append(
			"append_actions",
			{"append_to": "Contact", "trigger_on": "Incoming", **mapping},
		)
		return account

	def test_append_action_needs_the_sender_mappings(self):
		account = self._append_action(self._account("A"))

		with self.assertRaises(frappe.MandatoryError):
			account.save()

	def test_append_action_rejects_a_field_the_target_doctype_lacks(self):
		account = self._append_action(
			self._account("A"), sender_field="mobile_no", sender_name_field="no_such_field"
		)

		with self.assertRaises(frappe.ValidationError):
			account.save()

	def test_append_action_rejects_a_field_that_cannot_hold_the_value(self):
		# first_name is Data, and a timestamp needs a date field
		account = self._append_action(
			self._account("A"),
			sender_field="mobile_no",
			sender_name_field="first_name",
			timestamp_field="first_name",
		)

		with self.assertRaises(frappe.ValidationError):
			account.save()

	def test_append_action_rejects_a_child_table_target(self):
		account = self._append_action(
			self._account("A"), append_to="DocField", sender_field="fieldname", sender_name_field="label"
		)

		with self.assertRaisesRegex(frappe.ValidationError, "cannot append to DocField"):
			account.save()

	def test_append_action_rejects_a_single_target(self):
		account = self._append_action(
			self._account("A"),
			append_to="System Settings",
			sender_field="app_name",
			sender_name_field="app_name",
		)

		with self.assertRaisesRegex(frappe.ValidationError, "cannot append to System Settings"):
			account.save()

	def test_append_action_accepts_a_mapping_the_target_doctype_supports(self):
		account = self._append_action(
			self._account("A"), sender_field="mobile_no", sender_name_field="first_name"
		)

		account.save()

		self.assertEqual(account.append_actions[0].sender_field, "mobile_no")

	def test_field_options_only_offer_fields_that_can_hold_the_value(self):
		message_fields = {option["value"] for option in get_append_field_options("ToDo", "message_field")}
		timestamp_fields = {option["value"] for option in get_append_field_options("ToDo", "timestamp_field")}

		self.assertIn("description", message_fields)
		self.assertNotIn("date", message_fields)
		self.assertIn("date", timestamp_fields)
		self.assertNotIn("description", timestamp_fields)

	def test_field_options_are_filtered_by_what_was_typed(self):
		options = [
			option["value"] for option in get_append_field_options("Contact", "sender_field", txt="mobile")
		]

		self.assertIn("mobile_no", options)
		self.assertTrue(all("mobile" in option for option in options))

	def test_field_options_are_empty_until_a_doctype_is_chosen(self):
		self.assertEqual(get_append_field_options("", "sender_field"), [])

	@patch("whatsapp.whatsapp.doctype.wa_account.wa_account._get_whatsapp_client")
	def test_subscription_check_matches_the_expected_app(self, get_client):
		get_client.return_value.get_subscribed_apps.return_value = {
			"data": [{"whatsapp_business_api_data": {"id": "app_1", "name": "My App"}}]
		}
		account = self._account("1")
		account.db_set({"business_id": "waba_1", "app_id": "app_1"})

		result = check_webhook_subscription(account.name)

		self.assertTrue(result["subscribed"])
		self.assertEqual(result["subscribed_apps"][0]["name"], "My App")

	@patch("whatsapp.whatsapp.doctype.wa_account.wa_account._get_whatsapp_client")
	def test_subscription_check_reports_a_different_app_as_unsubscribed(self, get_client):
		get_client.return_value.get_subscribed_apps.return_value = {
			"data": [{"whatsapp_business_api_data": {"id": "app_1", "name": "Meta Test App"}}]
		}
		account = self._account("1")
		account.db_set({"business_id": "waba_1", "app_id": "app_9"})

		self.assertFalse(check_webhook_subscription(account.name)["subscribed"])

	def test_subscription_check_needs_a_business_id(self):
		account = self._account("1")
		self.assertRaises(frappe.ValidationError, check_webhook_subscription, account.name)

	@patch("whatsapp.whatsapp.doctype.wa_account.wa_account._get_whatsapp_client")
	def test_subscription_check_surfaces_meta_errors(self, get_client):
		get_client.return_value.get_subscribed_apps.side_effect = requests.HTTPError("Code 190: bad token")
		account = self._account("1")
		account.db_set("business_id", "waba_1")

		with self.assertRaises(frappe.ValidationError) as ctx:
			check_webhook_subscription(account.name)
		self.assertIn("Code 190", str(ctx.exception))

	@patch("whatsapp.whatsapp.doctype.wa_account.wa_account._get_whatsapp_client")
	def test_subscribe_posts_to_meta_then_rechecks(self, get_client):
		client = get_client.return_value
		client.subscribe_app.return_value = {"success": True}
		client.get_subscribed_apps.return_value = {
			"data": [{"whatsapp_business_api_data": {"id": "app_1", "name": "My App"}}]
		}
		account = self._account("1")
		account.db_set({"business_id": "waba_1", "app_id": "app_1"})

		result = subscribe_webhook(account.name)

		client.subscribe_app.assert_called_once_with()
		self.assertTrue(result["subscribed"])

	@patch("whatsapp.whatsapp.doctype.wa_account.wa_account._get_whatsapp_client")
	def test_subscribe_surfaces_meta_errors(self, get_client):
		get_client.return_value.subscribe_app.side_effect = requests.HTTPError("Code 200: missing permission")
		account = self._account("1")
		account.db_set("business_id", "waba_1")

		with self.assertRaises(frappe.ValidationError) as ctx:
			subscribe_webhook(account.name)
		self.assertIn("Code 200", str(ctx.exception))
