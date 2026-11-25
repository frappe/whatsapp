# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json

from frappe.tests import UnitTestCase

from whatsapp.whatsapp.flows.flow_json_fixtures import (
	CUSTOMER_PROFILE,
	CYCLIC,
	DEAL_FEEDBACK,
	LEAD_QUALIFICATION,
	ROUTED,
	complete,
	footer,
	screen,
)
from whatsapp.whatsapp.flows.outline import FlowOutline


class TestFlowOutline(UnitTestCase):
	def test_entry_screens_are_the_screens_no_navigate_reaches_with_their_declared_data(self):
		outline = FlowOutline.from_flow_json(json.dumps(DEAL_FEEDBACK)).as_dict()

		self.assertEqual(outline["screens"], ["WELCOME", "RATE", "DONE"])
		self.assertEqual(
			outline["entry_screens"], {"WELCOME": {"customer_name": "string", "product": "string"}}
		)

	def test_screen_titles_are_read_by_id_so_pickers_need_not_show_ids(self):
		flow = {"version": "7.3", "screens": [screen("WELCOME", [], title="Hello"), screen("DONE", [], title="")]}

		outline = FlowOutline.from_flow_json(flow).as_dict()

		self.assertEqual(outline["screen_titles"], {"WELCOME": "Hello"})

	def test_an_outline_stored_before_titles_were_read_still_loads(self):
		outline = FlowOutline.from_dict({"screens": ["A"], "entry_screens": {}, "answers": [], "sensitive": []})

		self.assertEqual(outline.screen_titles, {})

	def test_a_navigate_inside_an_if_branch_still_rules_out_its_target_as_an_entry(self):
		outline = FlowOutline.from_flow_json(LEAD_QUALIFICATION).as_dict()

		self.assertEqual(outline["entry_screens"], {"QUALIFY": {"lead_name": "string"}})

	def test_routing_model_targets_are_not_entry_screens(self):
		outline = FlowOutline.from_flow_json(ROUTED).as_dict()

		self.assertEqual(outline["entry_screens"], {"START": {"profile": "object", "count": "number"}})

	def test_an_entry_screen_without_data_declares_nothing(self):
		outline = FlowOutline.from_flow_json(CUSTOMER_PROFILE).as_dict()

		self.assertEqual(outline["entry_screens"], {"CONTACT": {}})

	def test_invalid_json_or_json_without_screens_is_refused(self):
		for flow_json in ("{not json", json.dumps({"version": "7.1"}), "[]"):
			with self.subTest(flow_json=flow_json), self.assertRaises(ValueError):
				FlowOutline.from_flow_json(flow_json)

	def test_data_passed_through_navigate_is_traced_back_to_the_input_that_filled_it(self):
		outline = FlowOutline.from_flow_json(DEAL_FEEDBACK).as_dict()

		self.assertEqual(
			outline["answers"],
			[
				{"key": "rating", "label": "Rate us", "component": "RadioButtonsGroup", "type": "string"},
				{"key": "comment", "label": "Comments", "component": "TextArea", "type": "string"},
			],
		)

	def test_answers_are_merged_across_outcomes_without_duplicates_or_the_flow_token(self):
		outline = FlowOutline.from_flow_json(LEAD_QUALIFICATION).as_dict()

		self.assertEqual(
			outline["answers"],
			[
				{"key": "outcome", "label": "", "component": "", "type": "unknown"},
				{"key": "email", "label": "Email", "component": "TextInput", "type": "string"},
				{"key": "company", "label": "Company", "component": "TextInput", "type": "string"},
				{"key": "budget", "label": "Budget", "component": "TextInput", "type": "number"},
				{"key": "passcode", "label": "Passcode", "component": "TextInput", "type": "string"},
				{"key": "reason", "label": "Why not?", "component": "Dropdown", "type": "string"},
				{"key": "summary", "label": "", "component": "", "type": "unknown"},
			],
		)

	def test_global_references_and_nested_payloads_become_typed_dotted_answers(self):
		outline = FlowOutline.from_flow_json(CUSTOMER_PROFILE).as_dict()

		self.assertEqual(
			outline["answers"],
			[
				{"key": "skipped", "label": "", "component": "", "type": "unknown"},
				{"key": "name", "label": "Full name", "component": "TextInput", "type": "string"},
				{"key": "address.city", "label": "City", "component": "TextInput", "type": "string"},
				{"key": "address.zip", "label": "ZIP", "component": "TextInput", "type": "number"},
				{"key": "interests", "label": "Interests", "component": "CheckboxGroup", "type": "array"},
				{"key": "agree", "label": "I agree to the terms", "component": "OptIn", "type": "boolean"},
				{"key": "photo", "label": "Your photo", "component": "PhotoPicker", "type": "media"},
			],
		)

	def test_a_navigate_cycle_ends_as_an_untraceable_answer(self):
		outline = FlowOutline.from_flow_json(CYCLIC).as_dict()

		self.assertEqual(outline["entry_screens"], {})
		self.assertEqual(outline["answers"], [{"key": "x", "label": "", "component": "", "type": "unknown"}])

	def test_sensitive_keys_are_answers_fed_by_listed_or_password_inputs(self):
		outline = FlowOutline.from_flow_json(LEAD_QUALIFICATION).as_dict()

		self.assertEqual(outline["sensitive"], ["budget", "passcode"])

	def test_sensitivity_follows_an_input_through_navigate(self):
		flow = json.loads(json.dumps(DEAL_FEEDBACK))
		flow["screens"][1]["sensitive"] = ["comment"]

		self.assertEqual(FlowOutline.from_flow_json(flow).sensitive, ["comment"])

	def test_a_traced_answer_replaces_an_earlier_untraced_one_for_the_same_key(self):
		flow = {
			"screens": [
				screen(
					"RATE",
					[
						{"type": "Dropdown", "name": "rating", "label": "Rating"},
						footer("Skip note", complete({"rating": "${form.rating}", "note": "none"})),
					],
				),
				screen(
					"NOTE",
					[
						{"type": "TextArea", "name": "note", "label": "Note"},
						footer("Send", complete({"rating": "fixed", "note": "${form.note}"})),
					],
					sensitive=["note"],
				),
			]
		}

		outline = FlowOutline.from_flow_json(flow)

		self.assertEqual(
			outline.answers,
			[
				{"key": "rating", "label": "Rating", "component": "Dropdown", "type": "string"},
				{"key": "note", "label": "Note", "component": "TextArea", "type": "string"},
			],
		)
		self.assertEqual(outline.sensitive, ["note"])

	def test_answer_types_follow_the_component(self):
		cases = [
			({"type": "DatePicker"}, "date"),
			({"type": "CalendarPicker"}, "date"),
			({"type": "CalendarPicker", "mode": "range"}, "object"),
			({"type": "ChipsSelector"}, "array"),
			({"type": "DocumentPicker"}, "media"),
			({"type": "TextInput", "input-type": "passcode"}, "string"),
			({"type": "RichText"}, "unknown"),
		]
		for component, expected in cases:
			flow = {
				"screens": [
					{
						"id": "ONLY",
						"layout": {
							"children": [
								{**component, "name": "field"},
								{
									"type": "Footer",
									"on-click-action": {
										"name": "complete",
										"payload": {"field": "${form.field}"},
									},
								},
							]
						},
					}
				]
			}
			with self.subTest(component=component):
				self.assertEqual(FlowOutline.from_flow_json(flow).answers[0]["type"], expected)

	def test_the_outline_round_trips_through_its_dict(self):
		outline = FlowOutline.from_flow_json(LEAD_QUALIFICATION)

		self.assertEqual(
			FlowOutline.from_dict(json.loads(json.dumps(outline.as_dict()))).as_dict(), outline.as_dict()
		)
