# Copyright (c) 2026, pratham@frappe.io and Contributors
# See license.txt

import json
import secrets
from unittest.mock import patch

import frappe
from frappe import _
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import get_or_create_profile

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = ["WhatsApp Account", "WhatsApp Template", "WhatsApp Profile"]


class IntegrationTestWhatsAppMessage(IntegrationTestCase):
	"""Integration tests for WhatsAppMessage."""

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
			account_name=f"_Test Account {uid}",
			status="Active",
			phone_id="1234567890",
			business_id="test_business",
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

	def _make_template(self, **overrides) -> str:
		uid = frappe.generate_hash(length=6)
		acc = self._make_account()
		data = dict(
			doctype="WhatsApp Template",
			template_label=f"_Test Template {uid}",
			template_name=f"_test_template_{uid}",
			template_type="UTILITY",
			language="en_US",
			message="Plain body text",
			whatsapp_account=acc,
			whatsapp_template_id=uid,
			template_variables=[],
		)
		data.update(overrides)
		doc = frappe.get_doc(data).insert()
		return doc.name

	def _make_outgoing(self, **overrides) -> dict:
		acc = overrides.pop("account", None) or self._make_account()
		from_val = overrides.pop("from_", None)
		phone = overrides.pop("_phone", None) or f"+1{secrets.randbelow(10**10):010d}"
		data = dict(
			doctype="WhatsApp Message",
			direction="Outgoing",
			whatsapp_account=acc,
		)
		if "to" in overrides:
			data["to"] = overrides.pop("to")
		else:
			data["to"] = self._make_profile(phone, acc)
		if from_val is not None:
			data["from"] = from_val
		data.update(overrides)
		return data

	def _make_setting(self):
		sett = frappe.get_single("WhatsApp Settings")
		sett.whatsapp_api_url = "https://graph.facebook.com"
		sett.whatsapp_api_version = "v22.0"
		sett.webhook_verify_token = "test_verify"
		sett.webhook_secret = "test_secret"
		sett.save()

	def _make_file(self, file_name: str = "test.png", content: bytes = b"fake_content") -> str:
		file_doc = frappe.get_doc(
			doctype="File",
			file_name=file_name,
			is_private=0,
			content=content,
		).insert(ignore_permissions=True)
		return file_doc.name

	# -------------------------------------------------------------------------
	# validate — outgoing
	# -------------------------------------------------------------------------

	def test_validate_outgoing_missing_to(self):
		data = self._make_outgoing(to="")
		doc = frappe.get_doc(data)
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_validate_outgoing_missing_account(self):
		data = self._make_outgoing()
		data["whatsapp_account"] = ""
		doc = frappe.get_doc(data)
		self.assertRaises(frappe.ValidationError, doc.validate)

	def test_validate_skipped_for_incoming(self):
		doc = frappe.get_doc(
			doctype="WhatsApp Message",
			direction="Incoming",
			**{"from": "+0987654321"},
		)
		doc.validate()  # no exception

	def test_on_trash_cascades_linked_logs(self):
		"""Deleting a WhatsApp Message must also delete its WhatsApp Log rows."""
		acc = self._make_account()
		phone = "+1555000111"
		profile = self._make_profile(phone, acc)
		msg = frappe.get_doc(
			doctype="WhatsApp Message",
			direction="Incoming",
			whatsapp_account=acc,
			to=profile,
			**{"from": phone},
		).insert(ignore_permissions=True)

		frappe.get_doc(
			doctype="WhatsApp Log",
			level="Info",
			event_type="Message",
			message="test log",
			reference_doctype="WhatsApp Message",
			reference_docname=msg.name,
		).insert(ignore_permissions=True)

		self.assertEqual(
			frappe.db.count(
				"WhatsApp Log",
				{"reference_doctype": "WhatsApp Message", "reference_docname": msg.name},
			),
			1,
		)

		frappe.delete_doc("WhatsApp Message", msg.name, ignore_permissions=True)

		self.assertFalse(frappe.db.exists("WhatsApp Message", msg.name))
		self.assertEqual(
			frappe.db.count(
				"WhatsApp Log",
				{"reference_doctype": "WhatsApp Message", "reference_docname": msg.name},
			),
			0,
		)

	def test_outgoing_fails_for_blocked_profile(self):
		acc = self._make_account()
		profile = self._make_profile("+1234567890", acc, "Blocked User")
		frappe.db.set_value("WhatsApp Profile", profile, "status", "Blocked")
		data = self._make_outgoing(account=acc)
		data["to"] = profile
		doc = frappe.get_doc(data)
		with self.assertRaises(frappe.ValidationError) as cm:
			doc.validate()
		self.assertIn("blocked profile", str(cm.exception).lower())

	# -------------------------------------------------------------------------
	# from auto-fill
	# -------------------------------------------------------------------------

	def test_set_from_number(self):
		data = self._make_outgoing()
		doc = frappe.get_doc(data)
		doc.validate()
		self.assertEqual(doc.get("from"), "1234567890")

	def test_set_from_number_skips_if_set(self):
		data = self._make_outgoing(from_="+1111111111")
		doc = frappe.get_doc(data)
		doc.validate()
		self.assertEqual(doc.get("from"), "+1111111111")

	# -------------------------------------------------------------------------
	# validate — template reference
	# -------------------------------------------------------------------------

	def test_template_reference_required_with_vars(self):
		tmpl = self._make_template(
			template_label="_Test Vars",
			template_name="_test_vars",
			message="Hello {{description}}",
			reference_doctype="ToDo",
			template_variables=[
				dict(
					variable_name="description",
					variable_example="ex",
					variable_field="description",
				),
			],
		)
		data = self._make_outgoing(is_template=1, whatsapp_template=tmpl)
		doc = frappe.get_doc(data)
		with self.assertRaises(frappe.ValidationError) as cm:
			doc.validate()
		self.assertIn("Reference Document", str(cm.exception))

	def test_template_reference_not_required_without_vars(self):
		tmpl = self._make_template(
			template_label="_Test NoVars",
			template_name="_test_novars",
			message="Hello, this is a plain message",
		)
		data = self._make_outgoing(is_template=1, whatsapp_template=tmpl)
		doc = frappe.get_doc(data)
		doc.validate()  # no exception

	def test_template_reference_not_checked_for_non_template(self):
		data = self._make_outgoing(message="Just text")
		doc = frappe.get_doc(data)
		doc.validate()  # no exception

	# -------------------------------------------------------------------------
	# parameter population
	# -------------------------------------------------------------------------

	def test_populate_template_parameters_body_only(self):
		todo = frappe.get_doc(doctype="ToDo", description="Buy milk").insert()
		tmpl = self._make_template(
			template_label="_Test PopBody",
			template_name="_test_popbody",
			message="Hello {{description}}",
			reference_doctype="ToDo",
			template_variables=[
				dict(
					variable_name="description",
					variable_example="ex",
					variable_field="description",
				),
			],
		)
		data = self._make_outgoing(
			is_template=1,
			whatsapp_template=tmpl,
			reference_doctype="ToDo",
			reference_docname=todo.name,
		)
		doc = frappe.get_doc(data)
		doc.validate()
		body = json.loads(doc.template_body_parameters or "{}")
		self.assertEqual(body, {"description": "Buy milk"})

	def test_populate_template_parameters_with_header(self):
		todo = frappe.get_doc(
			doctype="ToDo", description="Welcome!", sender="john@example.com"
		).insert()
		tmpl = self._make_template(
			template_label="_Test PopHead",
			template_name="_test_pophead",
			header_type="TEXT",
			header_text="{{description}}",
			message="Body {{sender}}",
			reference_doctype="ToDo",
			template_variables=[
				dict(
					variable_name="description",
					variable_example="Welcome",
					variable_field="description",
				),
				dict(
					variable_name="sender",
					variable_example="John",
					variable_field="sender",
				),
			],
		)
		data = self._make_outgoing(
			is_template=1,
			whatsapp_template=tmpl,
			reference_doctype="ToDo",
			reference_docname=todo.name,
		)
		doc = frappe.get_doc(data)
		doc.validate()
		body = json.loads(doc.template_body_parameters or "{}")
		self.assertEqual(body, {"sender": "john@example.com"})
		self.assertEqual(json.loads(doc.template_header_parameters), "Welcome!")

	def test_populate_template_parameters_skips_unmapped(self):
		todo = frappe.get_doc(doctype="ToDo", description="Buy milk").insert()
		tmpl = self._make_template(
			template_label="_Test Skip",
			template_name="_test_skip",
			message="Hello {{description}} and {{name}}",
			reference_doctype="ToDo",
			template_variables=[
				dict(
					variable_name="description",
					variable_example="ex",
					variable_field="description",
				),
				dict(variable_name="name", variable_example="John", variable_field=""),
			],
		)
		data = self._make_outgoing(
			is_template=1,
			whatsapp_template=tmpl,
			reference_doctype="ToDo",
			reference_docname=todo.name,
		)
		doc = frappe.get_doc(data)
		doc.validate()
		body = json.loads(doc.template_body_parameters or "{}")
		self.assertEqual(body, {"description": "Buy milk"})
		self.assertNotIn("name", body)

	# -------------------------------------------------------------------------
	# submit / send — notification events
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage.run_notifications")
	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_on_submit_fires_on_send(self, mock_send, mock_run_notif):
		mock_send.return_value = {"messages": [{"id": "wa_msg_on_send"}]}
		self._make_setting()

		data = self._make_outgoing(message="Hello from on_send test!")
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		mock_run_notif.assert_any_call("on_send")

	@patch("whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage.run_notifications")
	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_send_failure_fires_on_send_failed(self, mock_send, mock_run_notif):
		from requests import HTTPError

		mock_send.side_effect = HTTPError("API Error: Rate limit exceeded")
		self._make_setting()

		data = self._make_outgoing(message="Hello from failure test!")
		doc = frappe.get_doc(data)
		doc.insert()

		with self.assertRaises(frappe.ValidationError):
			doc.submit()

		mock_run_notif.assert_any_call("on_send_failed")

	# -------------------------------------------------------------------------
	# submit / send
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_submit_sends_template_message(self, mock_send):
		mock_send.return_value = {"messages": [{"id": "wa_msg_123"}]}
		self._make_setting()

		todo = frappe.get_doc(doctype="ToDo", description="Buy milk").insert()
		tmpl = self._make_template(
			template_label="_Test SubmitTmpl",
			template_name="_test_submittmpl",
			message="Hello {{description}}",
			reference_doctype="ToDo",
			template_variables=[
				dict(
					variable_name="description",
					variable_example="ex",
					variable_field="description",
				),
			],
		)
		data = self._make_outgoing(
			is_template=1,
			whatsapp_template=tmpl,
			reference_doctype="ToDo",
			reference_docname=todo.name,
		)
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		self.assertEqual(doc.status, "Sent")
		self.assertEqual(doc.message_id, "wa_msg_123")
		self.assertEqual(doc.docstatus, 1)
		mock_send.assert_called_once()

		payload = mock_send.call_args[0][0]
		self.assertEqual(payload["type"], "template")
		self.assertEqual(payload["template"]["name"], "_test_submittmpl")

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_submit_sends_text_message(self, mock_send):
		mock_send.return_value = {"messages": [{"id": "wa_msg_456"}]}
		self._make_setting()

		data = self._make_outgoing(message="Hello from test!")
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		self.assertEqual(doc.status, "Sent")
		self.assertEqual(doc.message_id, "wa_msg_456")
		mock_send.assert_called_once()

		payload = mock_send.call_args[0][0]
		self.assertEqual(payload["type"], "text")
		self.assertEqual(payload["text"]["body"], "Hello from test!")

	def test_submit_skipped_for_incoming(self):
		acc = self._make_account()
		profile = self._make_profile(f"+1{secrets.randbelow(10**10):010d}", acc)
		doc = frappe.get_doc(
			doctype="WhatsApp Message",
			to=profile,
			direction="Incoming",
			whatsapp_account=acc,
			**{"from": "+0987654321"},
			message="Incoming message",
		)
		doc.insert()
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_send_failure(self, mock_send):
		from requests import HTTPError

		mock_send.side_effect = HTTPError("API Error: Rate limit exceeded")
		self._make_setting()

		todo = frappe.get_doc(doctype="ToDo", description="Buy milk").insert()
		tmpl = self._make_template(
			template_label="_Test Fail",
			template_name="_test_fail",
			message="Hello {{description}}",
			reference_doctype="ToDo",
			template_variables=[
				dict(
					variable_name="description",
					variable_example="ex",
					variable_field="description",
				),
			],
		)
		data = self._make_outgoing(
			is_template=1,
			whatsapp_template=tmpl,
			reference_doctype="ToDo",
			reference_docname=todo.name,
		)
		doc = frappe.get_doc(data)
		doc.insert()

		with self.assertRaises(frappe.ValidationError):
			doc.submit()

		# Frappe sets docstatus=1 in Python before save(); DB should remain 0
		db_doc = frappe.get_doc("WhatsApp Message", doc.name)
		self.assertEqual(db_doc.docstatus, 0)
		# In-memory values set by _send before frappe.throw
		self.assertEqual(doc.status, "Failed")
		self.assertIn("Rate limit exceeded", doc.error_message)

	# -------------------------------------------------------------------------
	# reply-to / context
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_reply_to_message_resolves_context(self, mock_send):
		"""reply_to_message Link auto-fills context_message_id from the quoted message."""
		mock_send.return_value = {"messages": [{"id": "wa_reply_ctx"}]}
		self._make_setting()

		replied = frappe.get_doc(self._make_outgoing(message="Original", message_id="wamid.orig"))
		replied.insert()
		replied.submit()

		data = self._make_outgoing(message="Reply", reply_to_message=replied.name)
		doc = frappe.get_doc(data)
		doc.validate()
		self.assertEqual(doc.context_message_id, "wamid.orig")

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_context_included_in_outgoing_payload(self, mock_send):
		"""context.message_id is added to the send payload when context_message_id is set."""
		mock_send.return_value = {"messages": [{"id": "wa_ctx_001"}]}
		self._make_setting()

		data = self._make_outgoing(
			message="Hello with context",
			context_message_id="wamid.prev",
		)
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		payload = mock_send.call_args[0][0]
		self.assertIn("context", payload)
		self.assertEqual(payload["context"]["message_id"], "wamid.prev")

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_context_omitted_when_not_set(self, mock_send):
		"""Outgoing payload has no context key when context_message_id is empty."""
		mock_send.return_value = {"messages": [{"id": "wa_noctx_001"}]}
		self._make_setting()

		data = self._make_outgoing(message="No context")
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		payload = mock_send.call_args[0][0]
		self.assertNotIn("context", payload)

	# -------------------------------------------------------------------------
	# reactions
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_reaction_sends_reaction_payload(self, mock_send):
		"""Outgoing reaction with emoji sends type=reaction payload."""
		mock_send.return_value = {"messages": [{"id": "wa_rxn_001"}]}
		self._make_setting()

		data = self._make_outgoing(
			reaction="👍",
			context_message_id="wamid.target",
		)
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		payload = mock_send.call_args[0][0]
		self.assertEqual(payload["type"], "reaction")
		self.assertEqual(payload["reaction"]["emoji"], "👍")
		self.assertEqual(payload["reaction"]["message_id"], "wamid.target")

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_reaction_without_emoji_sends_unreact(self, mock_send):
		"""Empty reaction string sends un-react (no emoji key)."""
		mock_send.return_value = {"messages": [{"id": "wa_rxn_002"}]}
		self._make_setting()

		data = self._make_outgoing(
			reaction="",
			context_message_id="wamid.target",
		)
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		payload = mock_send.call_args[0][0]
		self.assertEqual(payload["type"], "reaction")
		self.assertNotIn("emoji", payload["reaction"])
		self.assertEqual(payload["reaction"]["message_id"], "wamid.target")

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_reaction_without_context_falls_to_text(self, mock_send):
		"""Reaction without context_message_id falls through to text message."""
		mock_send.return_value = {"messages": [{"id": "wa_rxn_003"}]}
		self._make_setting()

		data = self._make_outgoing(reaction="👍", message="Just text")
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		payload = mock_send.call_args[0][0]
		self.assertEqual(payload["type"], "text")

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_reaction_with_template_falls_to_template(self, mock_send):
		"""Reaction with is_template sends template, not reaction."""
		mock_send.return_value = {"messages": [{"id": "wa_rxn_004"}]}
		self._make_setting()

		tmpl = self._make_template(template_label="_Test Tmpl Rxn", template_name="_test_tmpl_rxn",
									 message="Template body")
		data = self._make_outgoing(
			is_template=1,
			whatsapp_template=tmpl,
			reaction="👍",
			context_message_id="wamid.target",
		)
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		payload = mock_send.call_args[0][0]
		self.assertEqual(payload["type"], "template")

	# -------------------------------------------------------------------------
	# media messages
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.upload_media")
	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_media_message_uploads_and_sends(self, mock_send, mock_upload):
		"""Media message uploads file then sends with correct media type."""
		mock_upload.return_value = {"id": "media_uploaded_001"}
		mock_send.return_value = {"messages": [{"id": "wa_med_001"}]}
		self._make_setting()

		file_name = self._make_file("photo.png", b"png_bytes")
		data = self._make_outgoing(attach=file_name)
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		mock_upload.assert_called_once()
		self.assertEqual(doc.media_id, "media_uploaded_001")

		payload = mock_send.call_args[0][0]
		self.assertEqual(payload["type"], "image")
		self.assertEqual(payload["image"]["id"], "media_uploaded_001")

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.upload_media")
	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_media_message_caption_in_payload(self, mock_send, mock_upload):
		"""Message field becomes caption in media payload."""
		mock_upload.return_value = {"id": "media_cap_001"}
		mock_send.return_value = {"messages": [{"id": "wa_med_002"}]}
		self._make_setting()

		file_name = self._make_file("document.bin", b"bin_bytes")
		data = self._make_outgoing(attach=file_name, message="Check this out")
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		payload = mock_send.call_args[0][0]
		self.assertEqual(payload["type"], "document")
		self.assertEqual(payload["document"]["caption"], "Check this out")

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.upload_media")
	def test_media_upload_failure_fails_send(self, mock_upload):
		"""Upload failure sets status=Failed and raises."""
		from requests import HTTPError

		mock_upload.side_effect = HTTPError("Upload rejected")
		self._make_setting()

		file_name = self._make_file("bad.bin", b"bad_bytes")
		data = self._make_outgoing(attach=file_name)
		doc = frappe.get_doc(data)
		doc.insert()

		with self.assertRaises(frappe.ValidationError):
			doc.submit()

		self.assertEqual(doc.status, "Failed")
		self.assertIn("Upload rejected", doc.error_message)

	def test_get_mime_type_maps_correctly(self):
		"""_get_mime_type returns correct MIME for known and unknown extensions."""
		doc = frappe.get_doc(doctype="WhatsApp Message", direction="Incoming", **{"from": "+1"})
		self.assertEqual(doc._get_mime_type("photo.jpg"), "image/jpeg")
		self.assertEqual(doc._get_mime_type("photo.jpeg"), "image/jpeg")
		self.assertEqual(doc._get_mime_type("photo.png"), "image/png")
		self.assertEqual(doc._get_mime_type("photo.webp"), "image/webp")
		self.assertEqual(doc._get_mime_type("video.mp4"), "video/mp4")
		self.assertEqual(doc._get_mime_type("audio.mp3"), "audio/mpeg")
		self.assertEqual(doc._get_mime_type("doc.pdf"), "application/pdf")
		self.assertEqual(doc._get_mime_type("doc.docx"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
		self.assertEqual(doc._get_mime_type("unknown.xyz"), "application/octet-stream")
		self.assertEqual(doc._get_mime_type("noext"), "application/octet-stream")

	# -------------------------------------------------------------------------
	# template header media upload
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.upload_media")
	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_template_header_media_uploaded_when_missing(self, mock_send, mock_upload):
		"""Template header media is uploaded on first send when handle missing."""
		mock_upload.return_value = {"id": "h_handle_001"}
		mock_send.return_value = {"messages": [{"id": "wa_th_001"}]}
		self._make_setting()

		file_name = self._make_file("header.png", b"header_bytes")
		tmpl = self._make_template(
			template_label="_Test Thm",
			template_name="_test_thm",
			header_type="IMAGE",
			header_media=file_name,
		)
		data = self._make_outgoing(is_template=1, whatsapp_template=tmpl)
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		mock_upload.assert_called_once()
		handle = frappe.db.get_value("WhatsApp Template", tmpl, "header_media_handle")
		self.assertEqual(handle, "h_handle_001")

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.upload_media")
	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_template_header_media_skipped_when_cached(self, mock_send, mock_upload):
		"""Template header media is NOT re-uploaded when handle already cached."""
		mock_send.return_value = {"messages": [{"id": "wa_th_002"}]}
		self._make_setting()

		file_name = self._make_file("header2.png", b"more_bytes")
		tmpl = self._make_template(
			template_label="_Test Thm2",
			template_name="_test_thm2",
			header_type="IMAGE",
			header_media=file_name,
			header_media_handle="existing_handle",
		)
		data = self._make_outgoing(is_template=1, whatsapp_template=tmpl)
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		mock_upload.assert_not_called()

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.upload_media")
	def test_template_header_media_upload_failure_fails_send(self, mock_upload):
		"""Template header media upload failure sets status=Failed and raises."""
		from requests import HTTPError

		mock_upload.side_effect = HTTPError("Header upload rejected")
		self._make_setting()

		file_name = self._make_file("fail.png", b"fail_bytes")
		tmpl = self._make_template(
			template_label="_Test Thm3",
			template_name="_test_thm3",
			header_type="IMAGE",
			header_media=file_name,
		)
		data = self._make_outgoing(is_template=1, whatsapp_template=tmpl)
		doc = frappe.get_doc(data)
		doc.insert()

		with self.assertRaises(frappe.ValidationError):
			doc.submit()

		self.assertEqual(doc.status, "Failed")
		self.assertIn("Header upload rejected", doc.error_message)

	# -------------------------------------------------------------------------
	# interactive messages
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_interactive_buttons_payload(self, mock_send):
		"""Interactive buttons produce correct payload structure."""
		mock_send.return_value = {"messages": [{"id": "wa_btn_001"}]}
		self._make_setting()

		data = self._make_outgoing(message="Pick one")
		data["interactive_buttons"] = [
			{"title": "Yes", "button_id": "btn_yes"},
			{"title": "No", "button_id": "btn_no"},
		]
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		payload = mock_send.call_args[0][0]
		self.assertEqual(payload["type"], "interactive")
		self.assertEqual(payload["interactive"]["type"], "button")
		self.assertEqual(len(payload["interactive"]["action"]["buttons"]), 2)
		self.assertEqual(payload["interactive"]["action"]["buttons"][0]["reply"]["title"], "Yes")

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_interactive_list_payload(self, mock_send):
		"""Interactive list produces correct payload structure."""
		mock_send.return_value = {"messages": [{"id": "wa_list_001"}]}
		self._make_setting()

		data = self._make_outgoing(message="Select from list")
		data["interactive_list_items"] = [
			{"title": "Option A", "description": "First option", "list_item_id": "opt_a"},
			{"title": "Option B", "description": "Second option", "list_item_id": "opt_b"},
		]
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		payload = mock_send.call_args[0][0]
		self.assertEqual(payload["type"], "interactive")
		self.assertEqual(payload["interactive"]["type"], "list")
		rows = payload["interactive"]["action"]["sections"][0]["rows"]
		self.assertEqual(len(rows), 2)
		self.assertEqual(rows[0]["title"], "Option A")

	def test_interactive_buttons_and_list_conflict(self):
		"""Setting both buttons and list items raises ValidationError."""
		data = self._make_outgoing(message="Conflict")
		data["interactive_buttons"] = [{"title": "Yes", "button_id": "y"}]
		data["interactive_list_items"] = [{"title": "A", "list_item_id": "a"}]
		doc = frappe.get_doc(data)
		with self.assertRaises(frappe.ValidationError) as cm:
			doc.validate()
		self.assertIn("Cannot have both", str(cm.exception))

	def test_interactive_max_buttons_exceeded(self):
		"""More than 3 buttons raises ValidationError."""
		data = self._make_outgoing(message="Too many")
		data["interactive_buttons"] = [
			{"title": f"B{i}", "button_id": f"b{i}"} for i in range(4)
		]
		doc = frappe.get_doc(data)
		with self.assertRaises(frappe.ValidationError) as cm:
			doc.validate()
		self.assertIn("Maximum 3", str(cm.exception))

	def test_interactive_max_list_items_exceeded(self):
		"""More than 10 list items raises ValidationError."""
		data = self._make_outgoing(message="Too many items")
		data["interactive_list_items"] = [
			{"title": f"I{i}", "list_item_id": f"i{i}"} for i in range(11)
		]
		doc = frappe.get_doc(data)
		with self.assertRaises(frappe.ValidationError) as cm:
			doc.validate()
		self.assertIn("Maximum 10", str(cm.exception))

	def test_interactive_max_buttons_allowed(self):
		"""Exactly 3 buttons passes validation."""
		data = self._make_outgoing(message="Three buttons")
		data["interactive_buttons"] = [
			{"title": f"B{i}", "button_id": f"b{i}"} for i in range(3)
		]
		doc = frappe.get_doc(data)
		doc.validate()  # no exception

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_interactive_buttons_with_template_falls_through(self, mock_send):
		"""Buttons with is_template sends template, not interactive."""
		mock_send.return_value = {"messages": [{"id": "wa_int_tmpl"}]}
		self._make_setting()

		tmpl = self._make_template(
			template_label="_Test IntTmpl",
			template_name="_test_inttmpl",
			message="Template body",
		)
		data = self._make_outgoing(is_template=1, whatsapp_template=tmpl)
		data["interactive_buttons"] = [{"title": "B1", "button_id": "b1"}]
		doc = frappe.get_doc(data)
		doc.insert()
		doc.submit()

		payload = mock_send.call_args[0][0]
		self.assertEqual(payload["type"], "template")

	# -------------------------------------------------------------------------
	# notify_change
	# -------------------------------------------------------------------------

	def _notify(self, **fields):
		doc = frappe.get_doc(dict(doctype="WhatsApp Message", **fields))
		with patch("frappe.publish_realtime") as publish:
			doc.notify_change()
		return publish

	def test_notify_change_is_scoped_to_the_reference_document(self):
		"""Without doctype/docname the event lands in the site room, i.e. every Desk user."""
		publish = self._notify(reference_doctype="ToDo", reference_docname="TODO-0001")

		event, message = publish.call_args[0]
		self.assertEqual(event, "whatsapp_message")
		self.assertEqual(message, {"reference_doctype": "ToDo", "reference_docname": "TODO-0001"})
		self.assertEqual(publish.call_args.kwargs["doctype"], "ToDo")
		self.assertEqual(publish.call_args.kwargs["docname"], "TODO-0001")
		self.assertTrue(publish.call_args.kwargs["after_commit"])

	def test_notify_change_publishes_nothing_without_a_reference(self):
		for fields in (
			{},
			{"reference_doctype": "ToDo"},
			{"reference_docname": "TODO-0001"},
		):
			with self.subTest(fields=fields):
				self._notify(**fields).assert_not_called()


class TestUtils:
	"""Tests for utility payload builders (no DB needed)."""

	def test_build_reaction_payload_with_emoji(self):
		from whatsapp.whatsapp.api.utils import build_reaction_message_payload

		result = build_reaction_message_payload(to="+123", message_id="wamid.x", emoji="🔥")
		assert result["type"] == "reaction"
		assert result["reaction"]["emoji"] == "🔥"
		assert result["reaction"]["message_id"] == "wamid.x"

	def test_build_reaction_payload_without_emoji(self):
		from whatsapp.whatsapp.api.utils import build_reaction_message_payload

		result = build_reaction_message_payload(to="+123", message_id="wamid.y", emoji=None)
		assert result["type"] == "reaction"
		assert "emoji" not in result["reaction"]

	def test_build_media_payload_image(self):
		from whatsapp.whatsapp.api.utils import build_media_message_payload

		result = build_media_message_payload(to="+123", media_id="mid_1", mime_type="image/png", caption="Nice pic")
		assert result["type"] == "image"
		assert result["image"]["id"] == "mid_1"
		assert result["image"]["caption"] == "Nice pic"

	def test_build_media_payload_document(self):
		from whatsapp.whatsapp.api.utils import build_media_message_payload

		result = build_media_message_payload(to="+123", media_id="mid_2", mime_type="application/pdf",
											 caption="Read this", file_name="report.pdf")
		assert result["type"] == "document"
		assert result["document"]["id"] == "mid_2"
		assert result["document"]["filename"] == "report.pdf"

	def test_build_media_payload_audio_no_caption(self):
		from whatsapp.whatsapp.api.utils import build_media_message_payload

		result = build_media_message_payload(to="+123", media_id="mid_3", mime_type="audio/mpeg")
		assert result["type"] == "audio"
		assert "caption" not in result["audio"]
		assert result["audio"]["id"] == "mid_3"

	def test_build_interactive_buttons_payload(self):
		from whatsapp.whatsapp.api.utils import build_interactive_buttons_payload

		result = build_interactive_buttons_payload(
			to="+123", body_text="Choose:",
			buttons=[{"id": "b1", "title": "One"}, {"id": "b2", "title": "Two"}],
		)
		assert result["type"] == "interactive"
		assert result["interactive"]["type"] == "button"
		assert len(result["interactive"]["action"]["buttons"]) == 2
		assert result["interactive"]["action"]["buttons"][0]["reply"]["id"] == "b1"

	def test_build_interactive_buttons_payload_with_footer(self):
		from whatsapp.whatsapp.api.utils import build_interactive_buttons_payload

		result = build_interactive_buttons_payload(
			to="+123", body_text="Choose:",
			buttons=[{"id": "b1", "title": "One"}],
			footer="Footer text",
		)
		assert result["interactive"]["footer"]["text"] == "Footer text"

	def test_build_interactive_list_payload(self):
		from whatsapp.whatsapp.api.utils import build_interactive_list_payload

		result = build_interactive_list_payload(
			to="+123", body_text="Pick:",
			items=[{"id": "i1", "title": "Item 1", "description": "Desc 1"}],
		)
		assert result["type"] == "interactive"
		assert result["interactive"]["type"] == "list"
		rows = result["interactive"]["action"]["sections"][0]["rows"]
		assert len(rows) == 1
		assert rows[0]["id"] == "i1"

	def test_build_interactive_list_payload_with_header(self):
		from whatsapp.whatsapp.api.utils import build_interactive_list_payload

		result = build_interactive_list_payload(
			to="+123", body_text="Pick:", header_text="Menu",
			items=[{"id": "i1", "title": "Item 1", "description": ""}],
		)
		assert result["interactive"]["header"]["text"] == "Menu"
