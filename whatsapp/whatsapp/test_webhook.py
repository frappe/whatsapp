# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import hashlib
import hmac
import json
import secrets
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.doctype.wa_profile.wa_profile import get_or_create_profile
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
			doctype="WA Account",
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
			doctype="WA Message",
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
		frappe.db.set_single_value("WA Settings", "webhook_verify_token", token)

		frappe.form_dict = frappe._dict(
			{
				"hub.mode": "subscribe",
				"hub.verify_token": token,
				"hub.challenge": "challenge_abc",
			}
		)
		self._bind_request("GET")
		result = handler()

		self.assertEqual(result.status_code, 200)
		self.assertEqual(result.mimetype, "text/plain")
		self.assertEqual(result.get_data(as_text=True), "challenge_abc")

	def test_handler_get_verification_rejects_bad_token(self):
		"""GET handler returns 403 text/plain when verify token doesn't match."""
		frappe.db.set_single_value("WA Settings", "webhook_verify_token", "correct_token")

		frappe.form_dict = frappe._dict(
			{
				"hub.mode": "subscribe",
				"hub.verify_token": "wrong_token",
				"hub.challenge": "challenge_abc",
			}
		)
		self._bind_request("GET")
		result = handler()

		self.assertEqual(result.status_code, 403)
		self.assertEqual(result.mimetype, "text/plain")
		self.assertEqual(result.get_data(as_text=True), "token mismatch")

	# -------------------------------------------------------------------------
	# on_receive
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.doctype.wa_message.wa_message.WAMessage.run_notifications")
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

		docstatus = frappe.db.get_value("WA Message", {"message_id": "wa_msg_submit_001"}, "docstatus")
		self.assertEqual(docstatus, 1)

	def test_repeated_messages_from_one_sender_share_one_record(self):
		"""A conversation opens one record through the append action; replies attach to it."""
		acc = self._make_account()
		account = frappe.get_doc("WA Account", acc)
		account.append(
			"append_actions",
			{
				"append_to": "Print Heading",
				"trigger_on": "Incoming",
				"sender_field": "description",
				"sender_name_field": "print_heading",
			},
		)
		account.save()
		sender = f"Repeat Sender {frappe.generate_hash(length=6)}"

		for index in range(3):
			_create_incoming_message(
				{
					"from": "14155552673",
					"id": f"wa_msg_repeat_{index}",
					"timestamp": "1700000000",
					"type": "text",
					"text": {"body": f"message {index}"},
				},
				acc,
				contact_profile={"name": sender},
			)

		created = frappe.get_all("Print Heading", filters={"print_heading": sender}, pluck="name")
		self.assertEqual(len(created), 1)
		self.assertEqual(frappe.db.get_value("Print Heading", created[0], "description"), "+14155552673")
		references = frappe.get_all(
			"WA Message",
			filters={"message_id": ("like", "wa_msg_repeat_%")},
			pluck="reference_docname",
		)
		self.assertEqual(references, [created[0]] * 3)

	def test_sender_id_that_is_also_a_valid_local_number_keeps_its_country_code(self):
		acc = self._make_account()
		with patch(
			"whatsapp.whatsapp.doctype.wa_profile.wa_profile.get_default_region",
			return_value="IN",
		):
			_create_incoming_message(
				{
					"from": "6591234567",
					"id": "wa_msg_foreign_001",
					"timestamp": "1700000000",
					"type": "text",
					"text": {"body": "hello from Singapore"},
				},
				acc,
			)

		profile = frappe.db.get_value("WA Message", {"message_id": "wa_msg_foreign_001"}, "to")
		self.assertEqual(frappe.db.get_value("WA Profile", profile, "phone_number"), "+6591234567")

	# -------------------------------------------------------------------------
	# on_status_update
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.doctype.wa_message.wa_message.WAMessage.run_notifications")
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
		self.assertEqual(frappe.db.get_value("WA Message", msg_name, "status"), "Delivered")

	@patch("whatsapp.whatsapp.doctype.wa_message.wa_message.WAMessage.run_notifications")
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
			doctype="WA Template",
			template_label=f"_Test Tmpl {uid}",
			template_name=f"_test_tmpl_{uid}",
			template_type="Utility",
			language="en_US",
			message="Hello",
			whatsapp_account=account,
			whatsapp_template_id=f"tmpl_id_{uid}",
		)
		data.update(overrides)
		doc = frappe.get_doc(data).insert()
		return doc.name

	@patch("whatsapp.whatsapp.doctype.wa_template.wa_template.WATemplate.run_notifications")
	def test_template_approved_fires_on_approved(self, mock_run_notif):
		"""_handle_template_status fires on_template_approved when APPROVED."""
		acc = self._make_account()
		tmpl_name = self._make_template(acc, status="Pending")

		value = {
			"message_template_id": frappe.db.get_value("WA Template", tmpl_name, "whatsapp_template_id"),
			"status": "APPROVED",
		}
		_handle_template_status(value)

		mock_run_notif.assert_any_call("on_template_approved")
		self.assertEqual(frappe.db.get_value("WA Template", tmpl_name, "status"), "Approved")

	@patch("whatsapp.whatsapp.doctype.wa_template.wa_template.WATemplate.run_notifications")
	def test_template_rejected_fires_on_rejected(self, mock_run_notif):
		"""_handle_template_status fires on_template_rejected when REJECTED."""
		acc = self._make_account()
		tmpl_name = self._make_template(acc, status="Pending")

		value = {
			"message_template_id": frappe.db.get_value("WA Template", tmpl_name, "whatsapp_template_id"),
			"status": "REJECTED",
		}
		_handle_template_status(value)

		mock_run_notif.assert_any_call("on_template_rejected")
		self.assertEqual(frappe.db.get_value("WA Template", tmpl_name, "status"), "Rejected")

	@patch("whatsapp.whatsapp.doctype.wa_template.wa_template.WATemplate.run_notifications")
	def test_template_skips_noop(self, mock_run_notif):
		"""_handle_template_status does NOT fire when status hasn't changed."""
		acc = self._make_account()
		tmpl_name = self._make_template(acc, status="Approved")

		value = {
			"message_template_id": frappe.db.get_value("WA Template", tmpl_name, "whatsapp_template_id"),
			"status": "APPROVED",
		}
		_handle_template_status(value)

		calls = [c.args[0] for c in mock_run_notif.call_args_list]
		self.assertNotIn("on_template_approved", calls)
		self.assertNotIn("on_template_rejected", calls)

	# -------------------------------------------------------------------------
	# incoming context_message_id
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.doctype.wa_message.wa_message.WAMessage.run_notifications")
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

		doc_name = frappe.db.get_value("WA Message", {"message_id": "wa_msg_ctx_001"}, "name")
		doc = frappe.get_doc("WA Message", doc_name)
		self.assertEqual(doc.context_message_id, "wamid.parent")

	# -------------------------------------------------------------------------
	# read receipts
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.mark_as_read")
	@patch("whatsapp.whatsapp.doctype.wa_message.wa_message.WAMessage.run_notifications")
	def test_read_receipt_sent_when_enabled(self, mock_run_notif, mock_mark_read):
		"""auto_read_receipts=True triggers mark_as_read for incoming messages."""
		acc = self._make_account()
		frappe.db.set_value("WA Account", acc, "auto_read_receipts", 1)

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
	@patch("whatsapp.whatsapp.doctype.wa_message.wa_message.WAMessage.run_notifications")
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
	@patch("whatsapp.whatsapp.doctype.wa_message.wa_message.WAMessage.run_notifications")
	def test_read_receipt_failure_does_not_raise(self, mock_run_notif, mock_mark_read):
		"""read receipt failure is logged but does not propagate."""
		mock_mark_read.side_effect = Exception("Connection error")
		acc = self._make_account()
		frappe.db.set_value("WA Account", acc, "auto_read_receipts", 1)

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

	@patch("whatsapp.whatsapp.doctype.wa_message.wa_message.WAMessage.run_notifications")
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

		doc_name = frappe.db.get_value("WA Message", {"message_id": "wa_reaction_001"}, "name")
		doc = frappe.get_doc("WA Message", doc_name)
		self.assertEqual(doc.reaction, "👍")
		self.assertEqual(doc.context_message_id, "wamid.target_msg")
		self.assertEqual(doc.message, "👍")

	@patch("whatsapp.whatsapp.doctype.wa_message.wa_message.WAMessage.run_notifications")
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

		doc_name = frappe.db.get_value("WA Message", {"message_id": "wa_reaction_002"}, "name")
		doc = frappe.get_doc("WA Message", doc_name)
		self.assertEqual(doc.reaction, "")
		self.assertEqual(doc.context_message_id, "wamid.target_msg2")


class TestWebhookSignature(IntegrationTestCase):
	"""POST signature checks: relayed by Central (per-account secret) and direct from Meta."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.db.set_single_value("WA Settings", "webhook_secret", "")
		self.addCleanup(self._unbind_request)

	def _unbind_request(self):
		try:
			del frappe.local.request
		except AttributeError:
			pass
		frappe.local.form_dict = frappe._dict()

	def _make_account(self, waba_id: str, secret: str | None) -> str:
		uid = frappe.generate_hash(length=6)
		return (
			frappe.get_doc(
				doctype="WA Account",
				account_name=f"_Test Sig Acc {uid}",
				status="Active",
				phone_id=f"phone_{uid}",
				business_id=waba_id,
				app_id="test_app",
				access_token="test_token",
				webhook_secret=secret,
			)
			.insert()
			.name
		)

	def _body(self, waba_id: str, phone_id: str) -> tuple[str, str]:
		message_id = f"wamid.{frappe.generate_hash(length=12)}"
		payload = {
			"object": "whatsapp_business_account",
			"entry": [
				{
					"id": waba_id,
					"changes": [
						{
							"field": "messages",
							"value": {
								"metadata": {"phone_number_id": phone_id},
								"contacts": [{"profile": {"name": "Relay Test"}}],
								"messages": [
									{
										"from": "14155550100",
										"id": message_id,
										"timestamp": "1700000000",
										"type": "text",
										"text": {"body": "hello via central"},
									}
								],
							},
						}
					],
				}
			],
		}
		# Central sends the same text it signs: frappe.as_json(body)
		return frappe.as_json(payload), message_id

	def _post(self, body: str, headers: dict):
		from werkzeug.test import EnvironBuilder
		from werkzeug.wrappers import Request

		env = EnvironBuilder(
			method="POST", data=body.encode(), headers=headers, content_type="application/json"
		).get_environ()
		frappe.local.request = Request(env)
		frappe.local.form_dict = frappe._dict(json.loads(body))
		return handler()

	@staticmethod
	def _sign(secret: str, body: str) -> str:
		return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

	def _relayed(self, secret: str):
		waba_id = f"waba_{frappe.generate_hash(length=8)}"
		account = self._make_account(waba_id, secret)
		phone_id = frappe.db.get_value("WA Account", account, "phone_id")
		body, message_id = self._body(waba_id, phone_id)
		return account, waba_id, body, message_id

	def test_valid_relayed_webhook_is_processed(self):
		account, _waba, body, message_id = self._relayed("acc-secret")
		# The site-wide secret of manual accounts does not apply to relayed webhooks.
		frappe.db.set_single_value("WA Settings", "webhook_secret", "manual-secret")

		result = self._post(body, {"X-Frappe-Central-Signature": f"sha256={self._sign('acc-secret', body)}"})

		self.assertEqual(result, "ok")
		self.assertEqual(
			frappe.db.get_value("WA Message", {"message_id": message_id}, "whatsapp_account"), account
		)

	def test_relayed_bare_hex_signature_is_accepted(self):
		_account, _waba, body, message_id = self._relayed("acc-secret")
		self._post(body, {"X-Frappe-Central-Signature": self._sign("acc-secret", body)})
		self.assertTrue(frappe.db.exists("WA Message", {"message_id": message_id}))

	def test_relayed_wrong_signature_is_rejected(self):
		_account, _waba, body, message_id = self._relayed("acc-secret")
		with self.assertRaises(frappe.PermissionError):
			self._post(body, {"X-Frappe-Central-Signature": self._sign("not-the-secret", body)})
		self.assertFalse(frappe.db.exists("WA Message", {"message_id": message_id}))

	def test_relayed_signature_with_another_accounts_secret_is_rejected(self):
		_account, _waba, body, message_id = self._relayed("acc-secret")
		self._make_account(f"waba_{frappe.generate_hash(length=8)}", "other-secret")
		with self.assertRaises(frappe.PermissionError):
			self._post(body, {"X-Frappe-Central-Signature": self._sign("other-secret", body)})
		self.assertFalse(frappe.db.exists("WA Message", {"message_id": message_id}))

	def test_relayed_signature_with_unknown_waba_is_rejected(self):
		body, message_id = self._body(f"waba_{frappe.generate_hash(length=8)}", "phone_x")
		with self.assertRaises(frappe.PermissionError):
			self._post(body, {"X-Frappe-Central-Signature": self._sign("acc-secret", body)})
		self.assertFalse(frappe.db.exists("WA Message", {"message_id": message_id}))

	def test_relayed_signature_for_account_without_secret_is_rejected(self):
		waba_id = f"waba_{frappe.generate_hash(length=8)}"
		account = self._make_account(waba_id, None)
		body, message_id = self._body(waba_id, frappe.db.get_value("WA Account", account, "phone_id"))
		with self.assertRaises(frappe.PermissionError):
			# Signed with an empty key: must not pass for an account that has no secret.
			self._post(body, {"X-Frappe-Central-Signature": self._sign("", body)})
		self.assertFalse(frappe.db.exists("WA Message", {"message_id": message_id}))

	def test_manual_path_checks_settings_secret_as_before(self):
		waba_id = f"waba_{frappe.generate_hash(length=8)}"
		account = self._make_account(waba_id, None)
		phone_id = frappe.db.get_value("WA Account", account, "phone_id")
		frappe.db.set_single_value("WA Settings", "webhook_secret", "manual-secret")

		body, message_id = self._body(waba_id, phone_id)
		with self.assertRaises(frappe.AuthenticationError):
			self._post(body, {"X-Hub-Signature-256": f"sha256={self._sign('wrong', body)}"})
		self.assertFalse(frappe.db.exists("WA Message", {"message_id": message_id}))

		body, message_id = self._body(waba_id, phone_id)
		self._post(body, {"X-Hub-Signature-256": f"sha256={self._sign('manual-secret', body)}"})
		self.assertTrue(frappe.db.exists("WA Message", {"message_id": message_id}))

	def test_unsigned_webhook_for_meta_connected_account_is_rejected(self):
		waba_id = f"waba_{frappe.generate_hash(length=8)}"
		account = self._make_account(waba_id, "central-secret")
		frappe.db.set_value("WA Account", account, "connected_with_meta", 1)
		phone_id = frappe.db.get_value("WA Account", account, "phone_id")

		# Named by its WABA id, and by its phone number under another WABA id.
		for entry_id in (waba_id, f"waba_{frappe.generate_hash(length=8)}"):
			body, message_id = self._body(entry_id, phone_id)
			with self.assertRaises(frappe.PermissionError):
				self._post(body, {})
			self.assertFalse(frappe.db.exists("WA Message", {"message_id": message_id}))

	def test_unsigned_webhook_routed_to_meta_connected_default_account_is_rejected(self):
		account = self._make_account(f"waba_{frappe.generate_hash(length=8)}", "central-secret")
		frappe.db.set_value("WA Account", account, "connected_with_meta", 1)
		frappe.db.set_single_value("WA Settings", "default_account", account)

		body, message_id = self._body(f"waba_{frappe.generate_hash(length=8)}", "phone_unknown")
		with self.assertRaises(frappe.PermissionError):
			self._post(body, {})
		self.assertFalse(frappe.db.exists("WA Message", {"message_id": message_id}))

	def test_manual_path_without_settings_secret_accepts_unsigned(self):
		waba_id = f"waba_{frappe.generate_hash(length=8)}"
		account = self._make_account(waba_id, None)
		body, message_id = self._body(waba_id, frappe.db.get_value("WA Account", account, "phone_id"))
		self._post(body, {})
		self.assertTrue(frappe.db.exists("WA Message", {"message_id": message_id}))

	def _connected_default_account(self) -> str:
		account = self._make_account(f"waba_{frappe.generate_hash(length=8)}", "central-secret")
		frappe.db.set_value("WA Account", account, "connected_with_meta", 1)
		frappe.db.set_single_value("WA Settings", "default_account", account)
		return account

	def test_unsigned_webhook_without_phone_id_for_meta_connected_default_account_is_rejected(self):
		self._connected_default_account()
		for metadata in ({}, {"phone_number_id": ""}):
			body, message_id = self._body(f"waba_{frappe.generate_hash(length=8)}", "unused")
			payload = json.loads(body)
			payload["entry"][0]["changes"][0]["value"]["metadata"] = metadata
			body = frappe.as_json(payload)
			with self.assertRaises(frappe.PermissionError):
				self._post(body, {})
			self.assertFalse(frappe.db.exists("WA Message", {"message_id": message_id}))

	def _unsigned_change(self, field: str, value: dict) -> str:
		entry = {
			"id": f"waba_{frappe.generate_hash(length=8)}",
			"changes": [{"field": field, "value": value}],
		}
		return frappe.as_json({"object": "whatsapp_business_account", "entry": [entry]})

	def test_unsigned_template_status_for_meta_connected_account_is_rejected(self):
		account = self._make_account(f"waba_{frappe.generate_hash(length=8)}", "central-secret")
		frappe.db.set_value("WA Account", account, "connected_with_meta", 1)
		template = TestWebhookNotifications._make_template(self, account, status="Pending")
		template_id = frappe.db.get_value("WA Template", template, "whatsapp_template_id")
		old_status = frappe.db.get_value("WA Template", template, "status")

		body = self._unsigned_change(
			"message_template_status_update", {"message_template_id": template_id, "status": "APPROVED"}
		)
		with self.assertRaises(frappe.PermissionError):
			self._post(body, {})
		self.assertEqual(frappe.db.get_value("WA Template", template, "status"), old_status)

	def test_unsigned_message_status_for_meta_connected_account_is_rejected(self):
		manual = self._make_account(f"waba_{frappe.generate_hash(length=8)}", None)
		connected = self._make_account(f"waba_{frappe.generate_hash(length=8)}", "central-secret")
		frappe.db.set_value("WA Account", connected, "connected_with_meta", 1)
		message_id = f"wamid.{frappe.generate_hash(length=12)}"
		message = TestWebhookNotifications._make_outgoing(
			self,
			connected,
			message_id=message_id,
			status="Sent",
			to=get_or_create_profile(
				phone_number=f"+1{secrets.randbelow(10**10):010d}", account_name=connected, profile_name="x"
			),
		)
		old_status = frappe.db.get_value("WA Message", message, "status")

		# Sent under the phone number of a manual account, which the check allows.
		body = self._unsigned_change(
			"messages",
			{
				"metadata": {"phone_number_id": frappe.db.get_value("WA Account", manual, "phone_id")},
				"statuses": [{"id": message_id, "status": "read"}],
			},
		)
		with self.assertRaises(frappe.PermissionError):
			self._post(body, {})
		self.assertEqual(frappe.db.get_value("WA Message", message, "status"), old_status)
