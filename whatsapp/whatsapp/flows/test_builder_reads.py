# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe

from whatsapp.whatsapp.flows.authoring import create_flow
from whatsapp.whatsapp.flows.builder_reads import get_flow_for_builder, get_flow_list
from whatsapp.whatsapp.flows.meta_fixtures import make_account
from whatsapp.whatsapp.flows.template_fixtures import flow_button
from whatsapp.whatsapp.flows.test_authoring import AuthoringCase


class IntegrationTestBuilderReads(AuthoringCase):
	def test_the_list_counts_the_templates_that_use_each_flow(self):
		used, unused = self.new_flow("Used"), self.new_flow("Unused")
		self.template_using(flow_button(used), flow_button(used, "Second button"))
		self.template_using(flow_button(used))

		rows = {row["name"]: row for row in get_flow_list(self.account)}

		self.assertEqual((rows[used]["used_by"], rows[unused]["used_by"]), (2, 0))
		self.assertEqual(rows[used]["categories"], ["LEAD_GENERATION"])
		self.assertEqual(rows[used]["flow_name"], "Used")

	def test_the_list_holds_the_flows_of_the_accounts_business_only(self):
		mine = self.new_flow("Mine")
		other = make_account()
		theirs = create_flow(other, "Theirs", ["SURVEY"])

		names = [row["name"] for row in get_flow_list(self.account)]

		self.assertIn(mine, names)
		self.assertNotIn(theirs, names)

	def test_used_keys_lists_the_templates_mapping_each_answer_and_input(self):
		name, other_flow = self.new_flow(), self.new_flow("Other")
		update_reference = {
			"action": "Update Reference",
			"fields": [
				{"source": "budget", "target_field": "notes"},
				{"source": "address.city", "target_field": "city"},
				{"source": "sender_phone", "target_field": "phone"},
			],
		}
		create_document = {
			"action": "Create Document",
			"doctype": "ToDo",
			"fields": [{"source": "budget", "target_field": "description"}],
		}
		first = self.template_using(
			flow_button(name, flow_response_actions=[update_reference]),
			flow_button(name, "Again", flow_inputs=[{"key": "full_name", "source_field": "first_name"}]),
		)
		second = self.template_using(
			flow_button(name, flow_response_actions=[create_document]),
			flow_button(
				other_flow, flow_response_actions=[{**create_document, "fields": [{"source": "other_key"}]}]
			),
		)

		builder = get_flow_for_builder(name)

		labels = {
			template: frappe.db.get_value("WA Template", template, "template_label")
			for template in (first, second)
		}
		self.assertEqual(
			builder["used_keys"],
			{
				"budget": sorted(
					[_ref(first, labels), _ref(second, labels)], key=lambda ref: ref["template_label"]
				),
				"address": [_ref(first, labels)],
			},
		)
		self.assertEqual(builder["used_inputs"], {"full_name": [_ref(first, labels)]})


def _ref(template: str, labels: dict) -> dict:
	return {"name": template, "template_label": labels[template]}
