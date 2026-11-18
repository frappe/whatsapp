# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
import requests
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.doctype.wa_template.wa_template import _upsert_template
from whatsapp.whatsapp.flows.flow_json_fixtures import LEAD_QUALIFICATION
from whatsapp.whatsapp.flows.template_fixtures import (
	flow_button,
	make_flow,
	meta_flow_button,
	meta_template,
	template_doc,
)
from whatsapp.whatsapp.flows.test_sync import CLIENT, FakeMeta, make_account

INPUTS = [{"key": "customer_name", "source_field": "first_name"}]
ACTIONS = [{"action": "Update Reference", "fields": [{"source": "comment", "target_field": "designation"}]}]


class IntegrationTestFlowButtonOnMeta(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.account = make_account()
		self.meta = FakeMeta()
		self.meta.client.create_template.side_effect = lambda payload: {
			"id": frappe.generate_hash(length=10),
			"status": "PENDING",
		}
		patcher = patch(CLIENT, return_value=self.meta.client)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_a_flow_button_is_created_on_meta_with_its_screen_and_icon(self):
		make_flow(self.account, "3001")
		template_doc(
			self.account,
			[{"button_type": "Quick Reply", "button_text": "Later"}, flow_button("3001", flow_icon="Review")],
		).insert()

		self.assertEqual(
			self._buttons_sent()[1],
			{
				"type": "FLOW",
				"text": "Give feedback",
				"flow_id": "3001",
				"flow_action": "navigate",
				"navigate_screen": "WELCOME",
				"icon": "REVIEW",
			},
		)

	def test_a_data_exchange_button_without_icon_sends_neither_icon_nor_an_empty_one(self):
		make_flow(self.account, "3002")
		template_doc(self.account, [flow_button("3002", flow_action="Data Exchange")]).insert()

		button = self._buttons_sent()[0]
		self.assertEqual(button["flow_action"], "data_exchange")
		self.assertNotIn("icon", button)

	def test_a_flow_button_without_a_screen_sends_none(self):
		make_flow(self.account, "3003", flow_json="{not json")
		template_doc(self.account, [flow_button("3003")]).insert()

		self.assertNotIn("navigate_screen", self._buttons_sent()[0])

	def _buttons_sent(self) -> list[dict]:
		payload = self.meta.client.create_template.call_args.args[0]
		return next(c["buttons"] for c in payload["components"] if c["type"] == "BUTTONS")


class IntegrationTestFlowButtonSync(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.account = make_account()
		self.meta = FakeMeta()
		patcher = patch(CLIENT, return_value=self.meta.client)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_a_meta_flow_button_syncs_with_its_flow_screen_action_and_icon(self):
		make_flow(self.account, "4001")
		buttons = [
			{"type": "QUICK_REPLY", "text": "Later"},
			meta_flow_button("4001", flow_action="data_exchange", navigate_screen="RATE", icon="PROMOTION"),
		]

		template = self._sync(meta_template("t4001", "_test_flow_sync_1", buttons))

		self.assertEqual(template.buttons[0].button_type, "Quick Reply")
		flow = template.buttons[1]
		self.assertEqual(
			(
				flow.button_type,
				flow.button_text,
				flow.flow,
				flow.flow_screen,
				flow.flow_action,
				flow.flow_icon,
			),
			("Flow", "Give feedback", "4001", "RATE", "Data Exchange", "Promotion"),
		)

	def test_a_meta_flow_button_with_only_its_flow_id_defaults_to_navigate(self):
		make_flow(self.account, "4002")

		flow = self._sync(meta_template("t4002", "_test_flow_sync_2", [meta_flow_button("4002")])).buttons[0]

		self.assertEqual(
			(flow.flow, flow.flow_screen, flow.flow_action, flow.flow_icon), ("4002", "", "Navigate", "")
		)

	def test_a_flow_not_synced_yet_is_synced_with_the_template(self):
		self.meta.add("4003", "Lead qualification", flow_json=LEAD_QUALIFICATION)

		flow = self._sync(meta_template("t4003", "_test_flow_sync_3", [meta_flow_button("4003")])).buttons[0]

		self.assertEqual(flow.flow, "4003")
		self.assertEqual(frappe.db.get_value("WA Flow", "4003", "flow_name"), "Lead qualification")

	def test_a_flow_that_cannot_be_synced_leaves_the_button_without_a_flow(self):
		self.meta.client.get_flow.side_effect = requests.HTTPError("100: Unsupported get request")
		buttons = [meta_flow_button("4004"), {"type": "URL", "text": "Website", "url": "https://example.com"}]

		template = self._sync(meta_template("t4004", "_test_flow_sync_4", buttons))

		self.assertEqual([b.button_type for b in template.buttons], ["Flow", "URL"])
		self.assertFalse(template.buttons[0].flow)
		self.assertTrue(
			frappe.db.exists(
				"WA Log", {"level": "Error", "event_type": "Template", "message": ("like", "%4004%")}
			)
		)

	def test_resync_keeps_the_local_inputs_and_actions_of_each_flow_button(self):
		make_flow(self.account, "4005")
		make_flow(self.account, "4006")
		meta = meta_template(
			"t4005", "_test_flow_sync_5", [meta_flow_button("4005"), meta_flow_button("4006")]
		)
		template = self._sync(meta)
		template.buttons[1].flow_inputs = json.dumps(INPUTS)
		template.buttons[1].flow_response_actions = json.dumps(ACTIONS)
		template.flags.from_sync = True
		template.save()
		meta["components"][1]["buttons"].reverse()

		template = self._sync(meta)

		self.assertEqual([b.flow for b in template.buttons], ["4006", "4005"])
		self.assertEqual(json.loads(template.buttons[0].flow_inputs), INPUTS)
		self.assertEqual(json.loads(template.buttons[0].flow_response_actions), ACTIONS)
		self.assertFalse(template.buttons[1].flow_inputs)

	def test_resync_keeps_the_configuration_of_a_button_whose_flow_was_replaced(self):
		make_flow(self.account, "4007")
		make_flow(self.account, "4008")
		meta = meta_template("t4007", "_test_flow_sync_7", [meta_flow_button("4007")])
		template = self._sync(meta)
		template.buttons[0].flow_inputs = json.dumps(INPUTS)
		template.flags.from_sync = True
		template.save()
		meta["components"][1]["buttons"] = [meta_flow_button("4008")]

		template = self._sync(meta)

		self.assertEqual(template.buttons[0].flow, "4008")
		self.assertEqual(json.loads(template.buttons[0].flow_inputs), INPUTS)

	def _sync(self, meta_payload: dict):
		_upsert_template(meta_payload, self.account)
		name = frappe.db.get_value(
			"WA Template", {"template_name": meta_payload["name"], "whatsapp_account": self.account}
		)
		return frappe.get_doc("WA Template", name)
