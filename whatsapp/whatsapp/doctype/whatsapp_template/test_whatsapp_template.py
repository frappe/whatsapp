# Copyright (c) 2026, pratham@frappe.io and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template import get_sendable_templates

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = ["WhatsApp Account"]


class IntegrationTestWhatsAppTemplate(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")

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

	def test_sync_preserves_local_variable_field(self):
		"""Hourly sync from Meta must not clobber user-configured variable_field mappings."""
		from whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template import _upsert_template

		account = self._make_account()
		uid = frappe.generate_hash(length=6)
		template_name = f"_test_var_field_{uid}"

		doc = frappe.get_doc(
			doctype="WhatsApp Template",
			template_label=template_name,
			template_name=template_name,
			template_type="UTILITY",
			language="en_US",
			message="Hello {{name}}, order {{order_id}}",
			whatsapp_account=account,
			whatsapp_template_id=uid,
			status="Pending",
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
		self.assertEqual(doc.status, "Approved")
		fields_by_name = {v.variable_name: v.variable_field for v in doc.template_variables}
		self.assertEqual(fields_by_name["name"], "full_name")
		self.assertEqual(fields_by_name["order_id"], "email")

	@patch("whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.WhatsApp")
	def test_push_to_meta_logs_without_link_validation_error_on_new_doc(self, MockWhatsApp):
		"""_push_to_meta runs in before_save (doc not yet in DB). Log writes must not
		fail with LinkValidationError trying to validate WhatsApp Template: <name>."""
		MockWhatsApp.return_value.create_template.return_value = {
			"id": "tmpl_123",
			"status": "PENDING",
		}

		account = self._make_account()
		uid = frappe.generate_hash(length=6)
		template_label = f"_Test Push {uid}"

		doc = frappe.get_doc(
			doctype="WhatsApp Template",
			template_label=template_label,
			template_name=f"_test_push_{uid}",
			template_type="UTILITY",
			language="en_US",
			message="Hello world",
			whatsapp_account=account,
		).insert()

		self.assertEqual(doc.whatsapp_template_id, "tmpl_123")
		self.assertEqual(doc.status, "Pending")

		log_exists = frappe.db.exists(
			"WhatsApp Log",
			{
				"event_type": "Template",
				"message": ["like", f"%{template_label}%pushed to Meta%"],
			},
		)
		self.assertTrue(log_exists, "expected a success WhatsApp Log row for the template push")

	def test_sync_leaves_variable_field_empty_for_new_variables(self):
		"""New variables introduced by Meta should start with empty variable_field."""
		from whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template import _upsert_template

		account = self._make_account()
		uid = frappe.generate_hash(length=6)
		template_name = f"_test_new_var_{uid}"

		frappe.get_doc(
			doctype="WhatsApp Template",
			template_label=template_name,
			template_name=template_name,
			template_type="UTILITY",
			language="en_US",
			message="Hello {{name}}",
			whatsapp_account=account,
			whatsapp_template_id=uid,
			status="Pending",
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

		doc = frappe.get_doc("WhatsApp Template", template_name)
		fields_by_name = {v.variable_name: v.variable_field for v in doc.template_variables}
		self.assertEqual(fields_by_name["name"], "full_name")
		self.assertEqual(fields_by_name.get("otp", ""), "")


class IntegrationTestGetSendableTemplates(IntegrationTestCase):
	"""Sendable means bound to the DocType, or unbound with no variables to resolve."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.account = self._make_account()
		self.uid = frappe.generate_hash(length=6)

	def _make_account(self) -> str:
		uid = frappe.generate_hash(length=6)
		return (
			frappe.get_doc(
				doctype="WhatsApp Account",
				account_name=f"_Test Sendable Acc {uid}",
				status="Active",
				phone_id="1234567890",
				business_id="test_business",
				app_id="test_app",
				access_token="test_token",
			)
			.insert()
			.name
		)

	def _make_template(
		self,
		suffix: str,
		*,
		status: str = "Approved",
		reference_doctype: str = "",
		message: str = "Hello there",
		template_variables: list | None = None,
		buttons: list | None = None,
	) -> str:
		name = f"_test_sendable_{suffix}_{self.uid}"
		return (
			frappe.get_doc(
				doctype="WhatsApp Template",
				template_label=name,
				template_name=name,
				template_type="UTILITY",
				language="en_US",
				message=message,
				whatsapp_account=self.account,
				# A template id short-circuits the push to Meta on insert.
				whatsapp_template_id=f"{suffix}_{self.uid}",
				status=status,
				variable_format="named",
				reference_doctype=reference_doctype,
				template_variables=template_variables or [],
				buttons=buttons or [],
			)
			.insert()
			.name
		)

	def test_only_approved_templates_are_returned(self):
		approved = self._make_template("approved", status="Approved", reference_doctype="ToDo")
		pending = self._make_template("pending", status="Pending", reference_doctype="ToDo")
		rejected = self._make_template("rejected", status="Rejected", reference_doctype="ToDo")

		names = [t.name for t in get_sendable_templates("ToDo")]
		self.assertIn(approved, names)
		self.assertNotIn(pending, names)
		self.assertNotIn(rejected, names)

	def test_templates_bound_to_another_doctype_are_excluded(self):
		other = self._make_template("otherdoctype", reference_doctype="Contact")
		self.assertNotIn(other, [t.name for t in get_sendable_templates("ToDo")])

	def test_unbound_template_without_variables_is_included(self):
		unbound = self._make_template("unbound_clean", reference_doctype="", message="No vars here")
		self.assertIn(unbound, [t.name for t in get_sendable_templates("ToDo")])

	def test_unbound_template_with_variables_is_excluded(self):
		"""Nothing can resolve its variables, so it must never reach the picker."""
		unbound = self._make_template(
			"unbound_vars",
			reference_doctype="",
			message="Hi {{first_name}}",
			template_variables=[
				{"variable_name": "first_name", "variable_example": "John", "variable_field": ""}
			],
		)
		self.assertNotIn(unbound, [t.name for t in get_sendable_templates("ToDo")])

	def test_bound_template_with_variables_is_included(self):
		bound = self._make_template(
			"bound_vars",
			reference_doctype="ToDo",
			message="Hi {{description}}",
			template_variables=[
				{
					"variable_name": "description",
					"variable_example": "Call back",
					"variable_field": "description",
				}
			],
		)
		self.assertIn(bound, [t.name for t in get_sendable_templates("ToDo")])

	def test_buttons_child_table_is_returned(self):
		"""`frappe.get_all` on the parent cannot return a child table; it needs its own query."""
		with_buttons = self._make_template(
			"buttons",
			reference_doctype="ToDo",
			buttons=[
				{"button_type": "URL", "button_text": "Track", "url": "https://example.com"},
				{"button_type": "PHONE_NUMBER", "button_text": "Call", "phone_number": "+15551230000"},
			],
		)
		template = next(t for t in get_sendable_templates("ToDo") if t.name == with_buttons)

		self.assertEqual(
			[(b["button_type"], b["button_text"]) for b in template["buttons"]],
			[("URL", "Track"), ("PHONE_NUMBER", "Call")],
		)
		self.assertEqual(template["buttons"][0]["url"], "https://example.com")
		self.assertEqual(template["buttons"][1]["phone_number"], "+15551230000")

	def test_template_without_buttons_gets_an_empty_list(self):
		plain = self._make_template("nobuttons", reference_doctype="ToDo")
		template = next(t for t in get_sendable_templates("ToDo") if t.name == plain)
		self.assertEqual(template["buttons"], [])


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
