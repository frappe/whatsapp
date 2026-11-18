# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.flows.flow_json_fixtures import CUSTOMER_PROFILE, ROUTED
from whatsapp.whatsapp.flows.meta_fixtures import FlowMetaCase, make_account
from whatsapp.whatsapp.flows.template_fixtures import flow_button, make_flow, template_doc
from whatsapp.whatsapp.mapping import get_input_source_fields, get_mappable_fields


def update_reference(*fields: tuple[str, str], **action) -> dict:
	return {
		"action": "Update Reference",
		"fields": [{"source": source, "target_field": target} for source, target in fields],
		**action,
	}


def create_document(doctype: str, *fields: tuple[str, str], **action) -> dict:
	return {**update_reference(*fields, **action), "action": "Create Document", "doctype": doctype}


class IntegrationTestFlowButtonValidation(FlowMetaCase):
	def setUp(self):
		super().setUp()
		self.feedback = make_flow(self.account, frappe.generate_hash(length=8)).name
		frappe.clear_messages()

	def test_a_valid_flow_button_is_saved_and_opens_on_the_first_entry_screen(self):
		template = self._save(
			flow_button(
				self.feedback,
				flow_inputs=[{"key": "customer_name", "source_field": "first_name"}],
				flow_response_actions=[
					update_reference(("rating", "designation"), ("sender_phone", "mobile_no")),
					create_document(
						"ToDo",
						("comment", "description"),
						("received_at", "date"),
						("reference_doctype", "reference_type"),
						("reference_name", "reference_name"),
						condition="response.get('rating') == '1'",
					),
				],
			)
		)

		self.assertEqual(template.buttons[0].flow_screen, "WELCOME")
		self.assertFalse(self._warnings())

	def test_a_button_without_a_flow_is_refused(self):
		self._assert_refused(flow_button(""), r"Button #1 \(Give feedback\): choose the Flow")

	def test_a_deprecated_flow_is_refused(self):
		deprecated = make_flow(self.account, frappe.generate_hash(length=8), status="Deprecated").name
		self._assert_refused(flow_button(deprecated), "is Deprecated")

	def test_a_flow_of_another_account_is_refused(self):
		other = make_flow(make_account(), frappe.generate_hash(length=8)).name
		self._assert_refused(flow_button(other), "belongs to another WhatsApp Business Account")

	def test_a_label_over_25_characters_is_refused(self):
		self._assert_refused(flow_button(self.feedback, text="Tell us how the deal went!!"), "25")

	def test_a_screen_that_is_not_an_entry_screen_is_refused(self):
		self._assert_refused(flow_button(self.feedback, flow_screen="RATE"), "RATE is not an entry screen")

	def test_a_flow_without_an_outline_is_saved_with_a_warning(self):
		draft = make_flow(self.account, frappe.generate_hash(length=8), flow_json="{not json").name

		template = self._save(
			flow_button(draft, flow_response_actions=[update_reference(("rating", "designation"))])
		)

		self.assertFalse(template.buttons[0].flow_screen)
		self.assertTrue(any("outline" in message for message in self._warnings()))

	def test_flow_inputs_need_a_reference_doctype(self):
		button = flow_button(
			self.feedback, flow_inputs=[{"key": "customer_name", "source_field": "first_name"}]
		)
		self._assert_refused(button, r"Flow input #1: .*Reference DocType", reference_doctype=None)

	def test_an_input_key_the_entry_screen_does_not_declare_is_refused(self):
		button = flow_button(self.feedback, flow_inputs=[{"key": "rating", "source_field": "first_name"}])
		self._assert_refused(button, r"Flow input #1: .*WELCOME does not declare rating")

	def test_an_input_from_a_missing_field_is_refused(self):
		button = flow_button(self.feedback, flow_inputs=[{"key": "product", "source_field": "no_such_field"}])
		self._assert_refused(button, r"Flow input #1: .*'no_such_field' does not exist on Contact")

	def test_an_input_from_a_field_of_the_wrong_type_is_refused(self):
		routed = make_flow(self.account, frappe.generate_hash(length=8), flow_json=ROUTED).name
		button = flow_button(routed, flow_inputs=[{"key": "count", "source_field": "first_name"}])
		self._assert_refused(button, r"Flow input #1: .*'first_name' is a Data field")

	def test_an_object_input_is_refused(self):
		routed = make_flow(self.account, frappe.generate_hash(length=8), flow_json=ROUTED).name
		button = flow_button(routed, flow_inputs=[{"key": "profile", "source_field": "first_name"}])
		self._assert_refused(button, r"Flow input #1: .*object")

	def test_an_unknown_action_kind_is_refused(self):
		button = flow_button(
			self.feedback, flow_response_actions=[{"action": "Delete Reference", "fields": []}]
		)
		self._assert_refused(button, r"Response action #1: .*Delete Reference")

	def test_update_reference_needs_a_reference_doctype(self):
		button = flow_button(
			self.feedback, flow_response_actions=[update_reference(("rating", "designation"))]
		)
		self._assert_refused(button, r"Response action #1: .*Reference DocType", reference_doctype=None)

	def test_create_document_needs_an_existing_doctype(self):
		button = flow_button(self.feedback, flow_response_actions=[create_document("No Such DocType")])
		self._assert_refused(button, r"Response action #1: .*No Such DocType")

	def test_create_document_refuses_a_child_table(self):
		button = flow_button(self.feedback, flow_response_actions=[create_document("DocField")])
		self._assert_refused(button, r"Response action #1: cannot append to DocField")

	def test_a_condition_that_is_not_a_python_expression_is_refused(self):
		button = flow_button(self.feedback, flow_response_actions=[update_reference(condition="rating = 5")])
		self._assert_refused(button, r"Response action #1: .*condition")

	def test_a_target_field_the_doctype_lacks_is_refused(self):
		button = flow_button(
			self.feedback, flow_response_actions=[update_reference(("rating", "no_such_field"))]
		)
		self._assert_refused(
			button, r"Response action #1, field #1: .*'no_such_field' does not exist on Contact"
		)

	def test_a_target_field_that_cannot_hold_the_answer_is_refused(self):
		profile = make_flow(self.account, frappe.generate_hash(length=8), flow_json=CUSTOMER_PROFILE).name
		button = flow_button(profile, flow_response_actions=[update_reference(("photo", "first_name"))])
		self._assert_refused(button, r"field #1: .*'first_name' is a Data field")

	def test_message_sources_need_a_field_that_can_hold_them(self):
		button = flow_button(
			self.feedback,
			flow_response_actions=[
				create_document("ToDo", ("comment", "description"), ("whole_response", "description"))
			],
		)
		self._assert_refused(button, r"Response action #1, field #2: .*'description' is a Text Editor field")

	def test_a_nested_answer_is_mapped_by_its_path(self):
		profile = make_flow(self.account, frappe.generate_hash(length=8), flow_json=CUSTOMER_PROFILE).name

		self._save(
			flow_button(
				profile,
				flow_response_actions=[
					update_reference(
						("address.city", "department"), ("agree", "unsubscribed"), ("photo", "image")
					)
				],
			)
		)

		self.assertFalse(self._warnings())

	def test_an_answer_the_flow_no_longer_sends_is_saved_with_a_warning(self):
		self._save(
			flow_button(self.feedback, flow_response_actions=[update_reference(("budget", "designation"))])
		)

		self.assertTrue(any("budget" in message for message in self._warnings()))

	def test_create_document_needs_create_permission_on_the_target(self):
		button = flow_button(self.feedback, flow_response_actions=[create_document("User")])
		self._assert_refused_for_author(button, r"Response action #1: .*create permission on User")

	def test_create_document_needs_write_access_to_each_target_field(self):
		button = flow_button(
			self.feedback,
			flow_response_actions=[
				create_document("Note", ("comment", "title"), ("received_at", "expire_notification_on"))
			],
		)
		self._assert_refused_for_author(
			button, r"Response action #1, field #2: .*'expire_notification_on' on Note"
		)

	def test_update_reference_needs_write_permission_on_the_reference(self):
		button = flow_button(
			self.feedback, flow_response_actions=[update_reference(("rating", "designation"))]
		)
		self._assert_refused_for_author(button, r"Response action #1: .*write permission on Contact")

	def test_update_reference_needs_write_access_to_each_target_field(self):
		button = flow_button(
			self.feedback,
			flow_response_actions=[
				update_reference(("comment", "location"), ("rating", "role_profile_name"))
			],
		)
		self._assert_refused_for_author(
			button, r"Response action #1, field #2: .*'role_profile_name' on User", reference_doctype="User"
		)

	def test_an_author_may_configure_what_they_can_write_themselves(self):
		frappe.set_user(self._author())
		self._save(
			flow_button(
				self.feedback, flow_response_actions=[create_document("ToDo", ("comment", "description"))]
			),
			reference_doctype="Note",
		)

	def _save(self, button: dict, **fields):
		return template_doc(self.account, [button], **fields).insert(ignore_permissions=True)

	def _assert_refused(self, button: dict, message: str, **fields) -> None:
		with self.assertRaisesRegex(frappe.ValidationError, message):
			self._save(button, **fields)
		self.meta.client.create_template.assert_not_called()

	def _assert_refused_for_author(self, button: dict, message: str, **fields) -> None:
		frappe.set_user(self._author())
		with self.assertRaisesRegex(frappe.ValidationError, message):
			self._save(button, **fields)

	def _author(self) -> str:
		"""A Desk User: creates Notes and ToDos but not Users, writes their own User but no permlevel 1 field.
		Templates are saved with ignore_permissions, so only the Response action checks apply."""
		user = frappe.get_doc(
			doctype="User",
			email=f"flow-author-{frappe.generate_hash(length=6)}@example.com",
			first_name="Author",
			roles=[{"role": "Desk User"}],
		).insert(ignore_permissions=True)
		return user.name

	def _warnings(self) -> list[str]:
		return [m["message"] for m in frappe.get_message_log() if m.get("indicator") == "orange"]


class IntegrationTestMappableFields(IntegrationTestCase):
	def test_fields_are_offered_only_when_they_can_hold_the_source(self):
		boolean_fields = {option["value"] for option in get_mappable_fields("Contact", "boolean")}
		doctype_fields = {option["value"] for option in get_mappable_fields("ToDo", "reference_doctype")}

		self.assertTrue({"is_primary_contact", "first_name"} <= boolean_fields)
		self.assertNotIn("image", boolean_fields)
		self.assertIn("reference_type", doctype_fields)
		self.assertNotIn("allocated_to", doctype_fields)

	def test_fields_are_filtered_by_what_was_typed(self):
		options = [option["value"] for option in get_mappable_fields("Contact", "string", txt="mobile")]

		self.assertEqual(options, ["mobile_no"])

	def test_an_unknown_source_type_offers_nothing(self):
		self.assertEqual(get_mappable_fields("Contact", "no_such_type"), [])

	def test_input_sources_are_offered_only_when_they_can_feed_the_declared_type(self):
		number_fields = {option["value"] for option in get_input_source_fields("User", "number")}
		boolean_fields = {option["value"] for option in get_input_source_fields("Contact", "boolean")}

		self.assertIn("simultaneous_sessions", number_fields)
		self.assertNotIn("first_name", number_fields)
		self.assertIn("is_primary_contact", boolean_fields)
		self.assertNotIn("first_name", boolean_fields)
		self.assertEqual(get_input_source_fields("Contact", "object"), [])
