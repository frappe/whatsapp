# Copyright (c) 2026, pratham@frappe.io and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
from frappe import _
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = ["Whatsapp Account", "Whatsapp Template"]


class IntegrationTestWhatsappMessage(IntegrationTestCase):
	"""Integration tests for WhatsappMessage."""

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
			account_name=f"_Test Account {uid}",
			status="Active",
			phone_id="1234567890",
			business_id="test_business",
			app_id="test_app",
			access_token="test_token",
		).insert()
		return doc.name

	def _make_template(self, **overrides) -> str:
		uid = frappe.generate_hash(length=6)
		acc = self._make_account()
		data = dict(
			doctype="Whatsapp Template",
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
		data = dict(
			doctype="Whatsapp Message",
			to="+1234567890",
			direction="Outgoing",
			whatsapp_account=acc,
		)
		if from_val is not None:
			data["from"] = from_val
		data.update(overrides)
		return data

	def _make_setting(self):
		sett = frappe.get_single("Whatsapp Setting")
		sett.whatsapp_api_url = "https://graph.facebook.com"
		sett.whatsapp_api_version = "v22.0"
		sett.webhook_verify_token = "test_verify"
		sett.webhook_secret = "test_secret"
		sett.save()

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
			doctype="Whatsapp Message",
			to="+1234567890",
			direction="Incoming",
			**{"from": "+0987654321"},
		)
		doc.validate()  # no exception

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
	# submit / send
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.api.whatsapp.Whatsapp.send_message")
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

	@patch("whatsapp.whatsapp.api.whatsapp.Whatsapp.send_message")
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
		doc = frappe.get_doc(
			doctype="Whatsapp Message",
			to="+1234567890",
			direction="Incoming",
			whatsapp_account=acc,
			**{"from": "+0987654321"},
			message="Incoming message",
		)
		doc.insert()
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	@patch("whatsapp.whatsapp.api.whatsapp.Whatsapp.send_message")
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
		db_doc = frappe.get_doc("Whatsapp Message", doc.name)
		self.assertEqual(db_doc.docstatus, 0)
		# In-memory values set by _send before frappe.throw
		self.assertEqual(doc.status, "Failed")
		self.assertIn("Rate limit exceeded", doc.error_message)
