# Copyright (c) 2026, pratham@frappe.io and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = ["Whatsapp Account"]


class IntegrationTestWhatsappTemplate(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")

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

	def test_sync_preserves_local_variable_field(self):
		"""Hourly sync from Meta must not clobber user-configured variable_field mappings."""
		from whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template import _upsert_template

		account = self._make_account()
		uid = frappe.generate_hash(length=6)
		template_name = f"_test_var_field_{uid}"

		doc = frappe.get_doc(
			doctype="Whatsapp Template",
			template_label=template_name,
			template_name=template_name,
			template_type="UTILITY",
			language="en_US",
			message="Hello {{name}}, order {{order_id}}",
			whatsapp_account=account,
			whatsapp_template_id=uid,
			status="PENDING",
			variable_format="named",
			reference_doctype="User",
			template_variables=[
				{"variable_name": "name", "variable_example": "John", "variable_field": "full_name"},
				{"variable_name": "order_id", "variable_example": "123", "variable_field": "email"},
			],
		).insert()

		meta_payload = {
			"id": uid,
			"name": template_name,
			"category": "UTILITY",
			"language": "en_US",
			"status": "APPROVED",
			"components": [
				{
					"type": "BODY",
					"text": "Hello {{name}}, order {{order_id}}",
					"example": {
						"body_text_named_params": [
							{"param_name": "name", "example": "John"},
							{"param_name": "order_id", "example": "123"},
						]
					},
				}
			],
		}
		_upsert_template(meta_payload, account)

		doc.reload()
		self.assertEqual(doc.status, "APPROVED")
		fields_by_name = {v.variable_name: v.variable_field for v in doc.template_variables}
		self.assertEqual(fields_by_name["name"], "full_name")
		self.assertEqual(fields_by_name["order_id"], "email")

	@patch("whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.Whatsapp")
	def test_push_to_meta_logs_without_link_validation_error_on_new_doc(self, MockWhatsapp):
		"""_push_to_meta runs in before_save (doc not yet in DB). Log writes must not
		fail with LinkValidationError trying to validate Whatsapp Template: <name>."""
		MockWhatsapp.return_value.create_template.return_value = {
			"id": "tmpl_123",
			"status": "PENDING",
		}

		account = self._make_account()
		uid = frappe.generate_hash(length=6)
		template_label = f"_Test Push {uid}"

		doc = frappe.get_doc(
			doctype="Whatsapp Template",
			template_label=template_label,
			template_name=f"_test_push_{uid}",
			template_type="UTILITY",
			language="en_US",
			message="Hello world",
			whatsapp_account=account,
		).insert()

		self.assertEqual(doc.whatsapp_template_id, "tmpl_123")
		self.assertEqual(doc.status, "PENDING")

		log_exists = frappe.db.exists(
			"Whatsapp Log",
			{
				"event_type": "Template",
				"message": ["like", f"%{template_label}%pushed to Meta%"],
			},
		)
		self.assertTrue(log_exists, "expected a success Whatsapp Log row for the template push")

	def test_sync_leaves_variable_field_empty_for_new_variables(self):
		"""New variables introduced by Meta should start with empty variable_field."""
		from whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template import _upsert_template

		account = self._make_account()
		uid = frappe.generate_hash(length=6)
		template_name = f"_test_new_var_{uid}"

		frappe.get_doc(
			doctype="Whatsapp Template",
			template_label=template_name,
			template_name=template_name,
			template_type="UTILITY",
			language="en_US",
			message="Hello {{name}}",
			whatsapp_account=account,
			whatsapp_template_id=uid,
			status="PENDING",
			variable_format="named",
			template_variables=[
				{"variable_name": "name", "variable_example": "John", "variable_field": "full_name"},
			],
		).insert()

		meta_payload = {
			"id": uid,
			"name": template_name,
			"category": "UTILITY",
			"language": "en_US",
			"status": "APPROVED",
			"components": [
				{
					"type": "BODY",
					"text": "Hello {{name}}, your code is {{otp}}",
					"example": {
						"body_text_named_params": [
							{"param_name": "name", "example": "John"},
							{"param_name": "otp", "example": "9999"},
						]
					},
				}
			],
		}
		_upsert_template(meta_payload, account)

		doc = frappe.get_doc("Whatsapp Template", template_name)
		fields_by_name = {v.variable_name: v.variable_field for v in doc.template_variables}
		self.assertEqual(fields_by_name["name"], "full_name")
		self.assertEqual(fields_by_name.get("otp", ""), "")


class TestUtils:
	"""Plain unit tests for utility functions (no DB needed)."""

	def test_get_template_variables_named(self):
		from whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template import get_template_variables

		result = get_template_variables("Hello {{name}}, your order {{order_id}}")
		assert result == ["name", "order_id"]

	def test_get_template_variables_positional(self):
		from whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template import get_template_variables

		result = get_template_variables("Hello {{1}}, your order {{2}}")
		assert result == ["1", "2"]

	def test_get_template_variables_empty(self):
		from whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template import get_template_variables

		assert get_template_variables("") == []
		assert get_template_variables(None) == []

	def test_get_template_variables_spacing(self):
		from whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template import get_template_variables

		result = get_template_variables("Hello {{ name }}")
		assert result == ["name"]

	def test_resolve_examples_positional_body(self):
		from whatsapp.whatsapp.api.utils import _resolve_examples

		comp = {"type": "BODY", "example": {"body_text": [["John", "123"]]}}
		text = "Hello {{1}}, order {{2}}"
		result = _resolve_examples(text, comp)
		assert result == [("1", "John"), ("2", "123")]

	def test_resolve_examples_positional_header(self):
		from whatsapp.whatsapp.api.utils import _resolve_examples

		comp = {"type": "HEADER", "example": {"header_text": ["Summer Sale"]}}
		text = "Our {{1}} is on!"
		result = _resolve_examples(text, comp)
		assert result == [("1", "Summer Sale")]

	def test_resolve_examples_named_body(self):
		from whatsapp.whatsapp.api.utils import _resolve_examples

		comp = {
			"type": "BODY",
			"example": {
				"body_text_named_params": [
					{"param_name": "name", "example": "John"},
					{"param_name": "order_id", "example": "123"},
				]
			},
		}
		text = "Hello {{name}}, order {{order_id}}"
		result = _resolve_examples(text, comp)
		assert result == [("name", "John"), ("order_id", "123")]

	def test_resolve_examples_named_header(self):
		from whatsapp.whatsapp.api.utils import _resolve_examples

		comp = {
			"type": "HEADER",
			"example": {"header_text_named_params": [{"param_name": "title", "example": "Welcome"}]},
		}
		text = "{{title}}"
		result = _resolve_examples(text, comp)
		assert result == [("title", "Welcome")]

	def test_resolve_examples_no_example(self):
		from whatsapp.whatsapp.api.utils import _resolve_examples

		comp = {"type": "BODY"}
		text = "Hello {{name}}"
		result = _resolve_examples(text, comp)
		assert result == [("name", "name")]

	def test_build_create_payload_named_format(self):
		from whatsapp.whatsapp.api.utils import build_create_template_payload

		doc = _make_mock_doc(
			template_name="test_template",
			language="en_US",
			template_type="UTILITY",
			message="Hello {{name}}",
			variable_format="named",
			template_variables_data=[("name", "John")],
		)
		payload = build_create_template_payload(doc)
		assert payload["parameter_format"] == "named"
		body = next(c for c in payload["components"] if c["type"] == "BODY")
		assert "body_text_named_params" in body["example"]
		assert body["example"]["body_text_named_params"] == [{"param_name": "name", "example": "John"}]

	def test_build_create_payload_positional_format(self):
		from whatsapp.whatsapp.api.utils import build_create_template_payload

		doc = _make_mock_doc(
			template_name="test_template",
			language="en_US",
			template_type="UTILITY",
			message="Hello {{1}}, order {{2}}",
			variable_format="positional",
			template_variables_data=[("1", "John"), ("2", "123")],
		)
		payload = build_create_template_payload(doc)
		assert "parameter_format" not in payload
		body = next(c for c in payload["components"] if c["type"] == "BODY")
		assert "body_text" in body["example"]
		assert body["example"]["body_text"] == [["John", "123"]]

	def test_build_create_payload_media_header(self):
		from whatsapp.whatsapp.api.utils import build_create_template_payload

		doc = _make_mock_doc(
			template_name="media_test",
			language="en_US",
			template_type="MARKETING",
			message="Check this out",
			header_type="IMAGE",
			header_media_handle="4::aW...",
		)
		payload = build_create_template_payload(doc)
		header = next(c for c in payload["components"] if c["type"] == "HEADER")
		assert header["format"] == "IMAGE"
		assert header["example"]["header_handle"] == ["4::aW..."]

	def test_build_create_payload_text_header_named(self):
		from whatsapp.whatsapp.api.utils import build_create_template_payload

		doc = _make_mock_doc(
			template_name="header_test",
			language="en_US",
			template_type="UTILITY",
			message="Body text",
			header_type="TEXT",
			header_text="Our {{title}}",
			variable_format="named",
			template_variables_data=[("title", "Summer Sale")],
		)
		payload = build_create_template_payload(doc)
		header = next(c for c in payload["components"] if c["type"] == "HEADER")
		assert header["format"] == "TEXT"
		assert "header_text_named_params" in header["example"]

	def test_parse_media_header_sync(self):
		from whatsapp.whatsapp.api.utils import parse_whatsapp_template_to_doc

		data = {
			"name": "media_template",
			"category": "MARKETING",
			"language": "en_US",
			"status": "APPROVED",
			"components": [
				{
					"type": "HEADER",
					"format": "IMAGE",
					"example": {"header_handle": ["4::aW..."]},
				},
				{"type": "BODY", "text": "Check this out"},
			],
		}
		result = parse_whatsapp_template_to_doc(data)
		assert result["header_media_handle"] == "4::aW..."
		assert result["header_type"] == "IMAGE"

	def test_parse_positional_vars_detection(self):
		from whatsapp.whatsapp.api.utils import parse_whatsapp_template_to_doc

		data = {
			"name": "pos_template",
			"category": "UTILITY",
			"language": "en_US",
			"status": "APPROVED",
			"components": [
				{
					"type": "BODY",
					"text": "Hello {{1}}, order {{2}}",
					"example": {"body_text": [["John", "123"]]},
				}
			],
		}
		result = parse_whatsapp_template_to_doc(data)
		assert result["variable_format"] == "positional"
		assert result["template_variables"][0]["variable_name"] == "1"

	def test_parse_named_vars_detection(self):
		from whatsapp.whatsapp.api.utils import parse_whatsapp_template_to_doc

		data = {
			"name": "named_template",
			"category": "UTILITY",
			"language": "en_US",
			"status": "APPROVED",
			"components": [
				{
					"type": "BODY",
					"text": "Hello {{name}}",
					"example": {"body_text_named_params": [{"param_name": "name", "example": "John"}]},
				}
			],
		}
		result = parse_whatsapp_template_to_doc(data)
		assert result["variable_format"] == "named"

	def test_build_message_payload_header_params_json_string(self):
		from whatsapp.whatsapp.api.utils import build_template_message_payload

		doc = _make_mock_doc(
			template_name="doc_test",
			language="en_US",
			template_type="UTILITY",
			message="Here is your document",
			header_type="DOCUMENT",
		)
		payload = build_template_message_payload(
			to="+1234567890",
			template_doc=doc,
			header_parameters='{"id": "media-id-123"}',
		)
		header_comp = next(c for c in payload["template"]["components"] if c["type"] == "header")
		assert header_comp["parameters"][0]["document"]["id"] == "media-id-123"


def _make_mock_doc(**kwargs):
	"""Build a simple object with attribute access to simulate a Frappe doc."""

	class MockDoc:
		def __init__(self, data):
			self.__dict__.update(data)
			if "template_variables_data" in data:
				self.template_variables = [
					MockDoc({"variable_name": v[0], "variable_example": v[1]})
					for v in data["template_variables_data"]
				]
				del self.template_variables_data
			else:
				self.template_variables = []
			if "buttons" not in data:
				self.buttons = []

	return MockDoc(kwargs)
