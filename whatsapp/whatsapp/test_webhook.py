# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import secrets

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import get_or_create_profile
from whatsapp.whatsapp.webhook import (
	_create_incoming_message,
	_handle_template_status,
	_update_message_status,
	handler,
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
			doctype="WhatsApp Account",
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
		phone = overrides.pop("_phone", None) or f"+1{secrets.randbelow(10**10):010d}"
		data = dict(
			doctype="WhatsApp Message",
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
	# handler dispatch (GET verification / POST receive)
	# -------------------------------------------------------------------------

	def _bind_request(self, method: str) -> None:
		"""Bind a mock request onto frappe.local so frappe.request resolves."""
		frappe.local.request = MagicMock(method=method)

		def _cleanup():
			try:
				del frappe.local.request
			except AttributeError:
				pass

		self.addCleanup(_cleanup)

	def test_handler_get_verification_echoes_challenge(self):
		"""GET handler must return raw text/plain Werkzeug Response with the challenge."""
		token = f"verify_{secrets.token_hex(8)}"
		frappe.db.set_single_value("WhatsApp Settings", "webhook_verify_token", token)

		frappe.form_dict = frappe._dict({
			"hub.mode": "subscribe",
			"hub.verify_token": token,
			"hub.challenge": "challenge_abc",
		})
		self._bind_request("GET")
		result = handler()

		self.assertEqual(result.status_code, 200)
		self.assertEqual(result.mimetype, "text/plain")
		self.assertEqual(result.get_data(as_text=True), "challenge_abc")

	def test_handler_get_verification_rejects_bad_token(self):
		"""GET handler returns 403 text/plain when verify token doesn't match."""
		frappe.db.set_single_value("WhatsApp Settings", "webhook_verify_token", "correct_token")

		frappe.form_dict = frappe._dict({
			"hub.mode": "subscribe",
			"hub.verify_token": "wrong_token",
			"hub.challenge": "challenge_abc",
		})
		self._bind_request("GET")
		result = handler()

		self.assertEqual(result.status_code, 403)
		self.assertEqual(result.mimetype, "text/plain")
		self.assertEqual(result.get_data(as_text=True), "token mismatch")

	# -------------------------------------------------------------------------
	# on_receive
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage.run_notifications")
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

	def test_incoming_message_is_submitted(self):
		"""Incoming messages are submitted (docstatus=1), not left as drafts."""
		acc = self._make_account()

		msg = {
			"from": "+1222222222",
			"id": "wa_msg_submit_001",
			"timestamp": "1700000000",
			"type": "text",
			"text": {"body": "Submit me"},
		}
		_create_incoming_message(msg, acc)

		docstatus = frappe.db.get_value(
			"WhatsApp Message", {"message_id": "wa_msg_submit_001"}, "docstatus"
		)
		self.assertEqual(docstatus, 1)

	# -------------------------------------------------------------------------
	# on_status_update
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage.run_notifications")
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
		self.assertEqual(frappe.db.get_value("WhatsApp Message", msg_name, "status"), "Delivered")

	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage.run_notifications")
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
			doctype="WhatsApp Template",
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

	@patch("whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.WhatsAppTemplate.run_notifications")
	def test_template_approved_fires_on_approved(self, mock_run_notif):
		"""_handle_template_status fires on_template_approved when APPROVED."""
		acc = self._make_account()
		tmpl_name = self._make_template(acc, status="Pending")

		value = {
			"message_template_id": frappe.db.get_value(
				"WhatsApp Template", tmpl_name, "whatsapp_template_id"
			),
			"status": "APPROVED",
		}
		_handle_template_status(value)

		mock_run_notif.assert_any_call("on_template_approved")
		self.assertEqual(
			frappe.db.get_value("WhatsApp Template", tmpl_name, "status"), "Approved"
		)

	@patch("whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.WhatsAppTemplate.run_notifications")
	def test_template_rejected_fires_on_rejected(self, mock_run_notif):
		"""_handle_template_status fires on_template_rejected when REJECTED."""
		acc = self._make_account()
		tmpl_name = self._make_template(acc, status="Pending")

		value = {
			"message_template_id": frappe.db.get_value(
				"WhatsApp Template", tmpl_name, "whatsapp_template_id"
			),
			"status": "REJECTED",
		}
		_handle_template_status(value)

		mock_run_notif.assert_any_call("on_template_rejected")
		self.assertEqual(
			frappe.db.get_value("WhatsApp Template", tmpl_name, "status"), "Rejected"
		)

	@patch("whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.WhatsAppTemplate.run_notifications")
	def test_template_skips_noop(self, mock_run_notif):
		"""_handle_template_status does NOT fire when status hasn't changed."""
		acc = self._make_account()
		tmpl_name = self._make_template(acc, status="Approved")

		value = {
			"message_template_id": frappe.db.get_value(
				"WhatsApp Template", tmpl_name, "whatsapp_template_id"
			),
			"status": "APPROVED",
		}
		_handle_template_status(value)

		calls = [c.args[0] for c in mock_run_notif.call_args_list]
		self.assertNotIn("on_template_approved", calls)
		self.assertNotIn("on_template_rejected", calls)

	# -------------------------------------------------------------------------
	# incoming context_message_id
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage.run_notifications")
	def test_incoming_context_message_id_from_context(self, mock_run_notif):
		"""Incoming message with context.id sets context_message_id on doc."""
		acc = self._make_account()

		msg = {
			"from": "+1111111112",
			"id": "wa_msg_ctx_001",
			"timestamp": "1700000000",
			"type": "text",
			"text": {"body": "Reply to something"},
			"context": {"id": "wamid.parent"},
		}
		_create_incoming_message(msg, acc)

		doc_name = frappe.db.get_value("WhatsApp Message", {"message_id": "wa_msg_ctx_001"}, "name")
		doc = frappe.get_doc("WhatsApp Message", doc_name)
		self.assertEqual(doc.context_message_id, "wamid.parent")

	# -------------------------------------------------------------------------
	# read receipts
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.mark_as_read")
	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage.run_notifications")
	def test_read_receipt_sent_when_enabled(self, mock_run_notif, mock_mark_read):
		"""auto_read_receipts=True triggers mark_as_read for incoming messages."""
		acc = self._make_account()
		frappe.db.set_value("WhatsApp Account", acc, "auto_read_receipts", 1)

		msg = {
			"from": "+12223334444",
			"id": "wa_rr_001",
			"timestamp": "1700000000",
			"type": "text",
			"text": {"body": "Hello"},
		}
		_create_incoming_message(msg, acc)

		mock_mark_read.assert_called_once()
		# Verify it was called with the correct message_id
		args, _ = mock_mark_read.call_args
		self.assertEqual(args[0], "wa_rr_001")

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.mark_as_read")
	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage.run_notifications")
	def test_read_receipt_not_sent_when_disabled(self, mock_run_notif, mock_mark_read):
		"""auto_read_receipts=False (default) does NOT call mark_as_read."""
		acc = self._make_account()
		# auto_read_receipts defaults to 0

		msg = {
			"from": "+12223334445",
			"id": "wa_rr_002",
			"timestamp": "1700000000",
			"type": "text",
			"text": {"body": "Hello"},
		}
		_create_incoming_message(msg, acc)

		mock_mark_read.assert_not_called()

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.mark_as_read")
	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage.run_notifications")
	def test_read_receipt_failure_does_not_raise(self, mock_run_notif, mock_mark_read):
		"""read receipt failure is logged but does not propagate."""
		mock_mark_read.side_effect = Exception("Connection error")
		acc = self._make_account()
		frappe.db.set_value("WhatsApp Account", acc, "auto_read_receipts", 1)

		msg = {
			"from": "+12223334446",
			"id": "wa_rr_003",
			"timestamp": "1700000000",
			"type": "text",
			"text": {"body": "Hello"},
		}
		# Should not raise
		_create_incoming_message(msg, acc)

	# -------------------------------------------------------------------------
	# incoming reactions
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage.run_notifications")
	def test_incoming_reaction_creates_reaction_message(self, mock_run_notif):
		"""Incoming reaction webhook creates message with reaction field and context_message_id."""
		acc = self._make_account()

		msg = {
			"from": "+15556667777",
			"id": "wa_reaction_001",
			"timestamp": "1700000000",
			"type": "reaction",
			"reaction": {
				"message_id": "wamid.target_msg",
				"emoji": "👍",
			},
		}
		_create_incoming_message(msg, acc)

		doc_name = frappe.db.get_value("WhatsApp Message", {"message_id": "wa_reaction_001"}, "name")
		doc = frappe.get_doc("WhatsApp Message", doc_name)
		self.assertEqual(doc.reaction, "👍")
		self.assertEqual(doc.context_message_id, "wamid.target_msg")
		self.assertEqual(doc.message, "👍")

	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage.run_notifications")
	def test_incoming_reaction_without_emoji(self, mock_run_notif):
		"""Incoming reaction without emoji still creates message with reaction set."""
		acc = self._make_account()

		msg = {
			"from": "+15556667778",
			"id": "wa_reaction_002",
			"timestamp": "1700000000",
			"type": "reaction",
			"reaction": {
				"message_id": "wamid.target_msg2",
			},
		}
		_create_incoming_message(msg, acc)

		doc_name = frappe.db.get_value("WhatsApp Message", {"message_id": "wa_reaction_002"}, "name")
		doc = frappe.get_doc("WhatsApp Message", doc_name)
		self.assertEqual(doc.reaction, "")
		self.assertEqual(doc.context_message_id, "wamid.target_msg2")
