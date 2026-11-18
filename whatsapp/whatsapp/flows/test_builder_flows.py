# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
from pathlib import Path

from frappe.tests import UnitTestCase

from whatsapp.whatsapp.flows import flow_json_fixtures
from whatsapp.whatsapp.flows.outline import FlowOutline

# Written by the Flow builder's model in @whatsapp/ui (ui/tests/flowBuilder/builderFlows.test.ts).
FLOW_JSON = Path(__file__).parent / "flow_json"


def load(group: str, name: str) -> dict:
	return json.loads((FLOW_JSON / group / f"{name}.json").read_text())


def answer(key: str, label: str, component: str, answer_type: str = "string") -> dict:
	return {"key": key, "label": label, "component": component, "type": answer_type}


class TestBuilderFlowsOutline(UnitTestCase):
	def test_a_two_screen_flow_traces_every_answer_and_declares_the_prefill(self):
		outline = FlowOutline.from_flow_json(load("builder", "lead_capture")).as_dict()

		self.assertEqual(outline["entry_screens"], {"YOUR_DETAILS": {"full_name": "string"}})
		self.assertEqual(
			outline["answers"],
			[
				answer("full_name", "Full name", "TextInput"),
				answer("email", "Email", "TextInput"),
				answer("budget", "Budget", "Dropdown"),
				answer("anything_else", "Anything else?", "TextArea"),
			],
		)
		self.assertEqual(outline["sensitive"], ["anything_else"])

	def test_each_question_kind_gets_its_answer_type(self):
		outline = FlowOutline.from_flow_json(load("builder", "feedback")).as_dict()

		self.assertEqual(outline["entry_screens"], {"FEEDBACK": {}})
		self.assertEqual(
			outline["answers"],
			[
				answer("how_was_it", "How was it?", "RadioButtonsGroup"),
				answer("what_did_you_like", "What did you like?", "CheckboxGroup", "array"),
				answer("visit_date", "Visit date", "DatePicker", "date"),
				answer("member_pin", "Member PIN", "TextInput"),
				answer("consent", "You may contact me", "OptIn", "boolean"),
			],
		)
		self.assertEqual(outline["sensitive"], ["member_pin"])

	def test_a_question_added_to_a_form_screen_joins_its_answers(self):
		outline = FlowOutline.from_flow_json(load("builder", "survey_edited")).as_dict()

		self.assertEqual(len(outline["answers"]), 10)
		self.assertEqual(outline["answers"][1], answer("tour_type", "Tour type", "RadioButtonsGroup"))
		self.assertEqual(outline["answers"][-1], answer("your_email", "Your email", "TextInput"))
		self.assertEqual(outline["sensitive"], [])

	def test_the_json_copies_of_the_outline_fixtures_match_them(self):
		for name in (
			"deal_feedback",
			"lead_qualification",
			"customer_profile",
			"cyclic",
			"routed",
			"prefilled",
		):
			with self.subTest(name=name):
				self.assertEqual(load("ours", name), getattr(flow_json_fixtures, name.upper()))
