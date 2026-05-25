# Copyright (c) 2026, pratham@frappe.io and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import get_or_create_profile
from whatsapp.whatsapp.webhook import (
	_create_incoming_message,
	_handle_template_status,
	_update_message_status,
)


class TestWebhookNotifications(IntegrationTestCase):
	"""Tests for notification events fired by webhook handlers."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")

	# -------------------------------------------------------------------------
	# helpers
	# -------------------------------------------------------------------------

	def _make_account(self) -> str:
		uid = frappe.generate_hash(length=6)
		doc = frappe.get_doc(
			doctype="Whatsapp Account",
			account_name=f"_Test Wh Acc {uid}",
			status="Active",
			phone_id=f"phone_{uid}",
			business_id="test_biz",
			app_id="test_app",
			access_token="test_token",
		).insert()
		return doc.name

	def _make_profile(self, phone: str, account: str, profile_name: str | None = None) -> str:
		return get_or_create_profile(
			phone_number=phone,
			account_name=account,
			profile_name=profile_name or phone,
		)

	def _make_outgoing(self, account: str, **overrides) -> str:
		phone = overrides.pop("_phone", "+1234567890")
		data = dict(
			doctype="Whatsapp Message",
			direction="Outgoing",
			whatsapp_account=account,
		)
		if "to" in overrides:
			data["to"] = overrides.pop("to")
		else:
			data["to"] = self._make_profile(phone, account)
		data.update(overrides)
		doc = frappe.get_doc(data).insert()
		return doc.name

	# -------------------------------------------------------------------------
	# on_receive
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsappMessage.run_notifications")
	def test_on_receive_notification(self, mock_run_notif):
		"""_create_incoming_message fires run_notifications("on_receive")."""
		acc = self._make_account()

		msg = {
			"from": "+1111111111",
			"id": "wa_msg_recv_001",
			"timestamp": "1700000000",
			"type": "text",
			"text": {"body": "Hello from test!"},
		}
		_create_incoming_message(msg, acc)

		mock_run_notif.assert_any_call("on_receive")

	# -------------------------------------------------------------------------
	# on_status_update
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsappMessage.run_notifications")
	def test_on_status_update_fires_on_change(self, mock_run_notif):
		"""_update_message_status fires run_notifications("on_status_update") on status change."""
		acc = self._make_account()
		msg_name = self._make_outgoing(acc, message_id="wa_msg_st_001", status="Sent")

		status = {
			"id": "wa_msg_st_001",
			"status": "delivered",
			"timestamp": "1700000001",
			"conversation": {"id": "conv_001"},
		}
		_update_message_status(status)

		mock_run_notif.assert_any_call("on_status_update")
		self.assertEqual(frappe.db.get_value("Whatsapp Message", msg_name, "status"), "Delivered")

	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsappMessage.run_notifications")
	def test_on_status_update_skips_noop(self, mock_run_notif):
		"""_update_message_status does NOT fire when status hasn't changed."""
		acc = self._make_account()
		self._make_outgoing(acc, message_id="wa_msg_st_002", status="Delivered")

		status = {
			"id": "wa_msg_st_002",
			"status": "delivered",
		}
		_update_message_status(status)

		calls = [c.args[0] for c in mock_run_notif.call_args_list]
		self.assertNotIn("on_status_update", calls)

	# -------------------------------------------------------------------------
	# on_template_approved / on_template_rejected
	# -------------------------------------------------------------------------

	def _make_template(self, account: str, **overrides) -> str:
		uid = frappe.generate_hash(length=6)
		data = dict(
			doctype="Whatsapp Template",
			template_label=f"_Test Tmpl {uid}",
			template_name=f"_test_tmpl_{uid}",
			template_type="UTILITY",
			language="en_US",
			message="Hello",
			whatsapp_account=account,
			whatsapp_template_id=f"tmpl_id_{uid}",
		)
		data.update(overrides)
		doc = frappe.get_doc(data).insert()
		return doc.name

	@patch("whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.WhatsappTemplate.run_notifications")
	def test_template_approved_fires_on_approved(self, mock_run_notif):
		"""_handle_template_status fires on_template_approved when APPROVED."""
		acc = self._make_account()
		tmpl_name = self._make_template(acc, status="PENDING")

		value = {
			"message_template_id": frappe.db.get_value(
				"Whatsapp Template", tmpl_name, "whatsapp_template_id"
			),
			"status": "APPROVED",
		}
		_handle_template_status(value)

		mock_run_notif.assert_any_call("on_template_approved")
		self.assertEqual(
			frappe.db.get_value("Whatsapp Template", tmpl_name, "status"), "APPROVED"
		)

	@patch("whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.WhatsappTemplate.run_notifications")
	def test_template_rejected_fires_on_rejected(self, mock_run_notif):
		"""_handle_template_status fires on_template_rejected when REJECTED."""
		acc = self._make_account()
		tmpl_name = self._make_template(acc, status="PENDING")

		value = {
			"message_template_id": frappe.db.get_value(
				"Whatsapp Template", tmpl_name, "whatsapp_template_id"
			),
			"status": "REJECTED",
		}
		_handle_template_status(value)

		mock_run_notif.assert_any_call("on_template_rejected")
		self.assertEqual(
			frappe.db.get_value("Whatsapp Template", tmpl_name, "status"), "REJECTED"
		)

	@patch("whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.WhatsappTemplate.run_notifications")
	def test_template_skips_noop(self, mock_run_notif):
		"""_handle_template_status does NOT fire when status hasn't changed."""
		acc = self._make_account()
		tmpl_name = self._make_template(acc, status="APPROVED")

		value = {
			"message_template_id": frappe.db.get_value(
				"Whatsapp Template", tmpl_name, "whatsapp_template_id"
			),
			"status": "APPROVED",
		}
		_handle_template_status(value)

		calls = [c.args[0] for c in mock_run_notif.call_args_list]
		self.assertNotIn("on_template_approved", calls)
		self.assertNotIn("on_template_rejected", calls)
