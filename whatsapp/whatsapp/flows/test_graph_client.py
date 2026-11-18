# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.api.whatsapp import WhatsApp
from whatsapp.whatsapp.flows.meta_fixtures import flow_list, flow_row

REQUESTS = "whatsapp.whatsapp.api.whatsapp.requests"


def response(body: dict | None = None, text: str = "") -> MagicMock:
	return MagicMock(json=MagicMock(return_value=body), text=text)


class IntegrationTestFlowGraphCalls(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.client = WhatsApp(
			frappe._dict(business_id="waba_1", app_id="app", access_token="secret", phone_number_id="phone")
		)

	def test_get_flows_follows_the_paging_cursor_to_the_last_page(self):
		with patch(REQUESTS) as requests:
			requests.request.side_effect = [
				response(flow_list(flow_row("1", "First"), after="CURSOR_2")),
				response(flow_list(flow_row("2", "Second"))),
			]

			flows = self.client.get_flows()

		self.assertEqual([flow["id"] for flow in flows], ["1", "2"])
		first_call, second_call = requests.request.call_args_list
		self.assertTrue(first_call.args[1].endswith("/waba_1/flows"))
		self.assertEqual(second_call.kwargs["params"], {"after": "CURSOR_2"})

	def test_the_flow_json_is_downloaded_from_the_presigned_url_without_the_access_token(self):
		with patch(REQUESTS) as requests:
			requests.get.return_value = response(text='{"version": "7.3", "screens": []}')

			flow_json = self.client.download_flow_json("https://scontent.xx.fbcdn.net/flow.json?sig=1")

		self.assertEqual(flow_json, '{"version": "7.3", "screens": []}')
		self.assertNotIn("secret", str(requests.get.call_args))

	def test_flow_json_is_uploaded_as_a_multipart_flow_json_asset(self):
		with patch(REQUESTS) as requests:
			requests.request.return_value = response({"success": True, "validation_errors": []})

			self.client.update_flow_json("7001", '{"screens": []}')

		call = requests.request.call_args
		self.assertTrue(call.args[1].endswith("/7001/assets"))
		self.assertEqual(
			call.kwargs["files"],
			{
				"file": ("flow.json", '{"screens": []}', "application/json"),
				"name": (None, "flow.json"),
				"asset_type": (None, "FLOW_JSON"),
			},
		)
		self.assertNotIn("Content-Type", call.kwargs["headers"])

	def test_a_flow_is_created_on_the_business_account_with_only_the_fields_given(self):
		with patch(REQUESTS) as requests:
			requests.request.return_value = response({"id": "7002"})

			created = self.client.create_flow("Lead form", ["LEAD_GENERATION"], clone_flow_id="7001")

		self.assertEqual(created, {"id": "7002"})
		call = requests.request.call_args
		self.assertEqual(call.args[0], "POST")
		self.assertTrue(call.args[1].endswith("/waba_1/flows"))
		self.assertEqual(
			call.kwargs["json"],
			{"name": "Lead form", "categories": ["LEAD_GENERATION"], "clone_flow_id": "7001"},
		)

	def test_a_flow_is_deleted_by_its_id(self):
		with patch(REQUESTS) as requests:
			requests.request.return_value = response({"success": True})

			self.client.delete_flow("7001")

		call = requests.request.call_args
		self.assertEqual(call.args[0], "DELETE")
		self.assertTrue(call.args[1].endswith("/7001"))
