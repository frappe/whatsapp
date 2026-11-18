# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from frappe.tests import UnitTestCase

from whatsapp.whatsapp.flows.flow_json_fixtures import load
from whatsapp.whatsapp.flows.outline import FlowOutline

# The builder/ fixtures are Flow JSON as written by the Flow builder in @whatsapp/ui.


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
