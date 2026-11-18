# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
import requests
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.flows.flow_json_fixtures import DEAL_FEEDBACK, LEAD_QUALIFICATION
from whatsapp.whatsapp.flows.manage import deprecate_flow, publish_flow, refresh_flow
from whatsapp.whatsapp.flows.meta_fixtures import flow_json_upload, validation_error
from whatsapp.whatsapp.flows.sync import sync_flows
from whatsapp.whatsapp.flows.test_sync import CLIENT, FakeMeta, make_account

FLOW_ID = "7001"


class IntegrationTestManageFlows(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.account = make_account()
		self.meta = FakeMeta()
		self.client = self.meta.client
		self.client.update_flow_json.return_value = flow_json_upload()
		self.client.publish_flow.return_value = {"success": True}
		self.client.deprecate_flow.return_value = {"success": True}
		patcher = patch(CLIENT, return_value=self.client)
		patcher.start()
		self.addCleanup(patcher.stop)

	def synced_flow(self, status: str = "DRAFT", **details):
		self.meta.add(FLOW_ID, "Deal feedback", status=status, **details)
		sync_flows(self.account)
		return frappe.get_doc("WA Flow", FLOW_ID)

	def edit(self, flow, flow_json: dict | str = LEAD_QUALIFICATION):
		flow.flow_json = flow_json if isinstance(flow_json, str) else json.dumps(flow_json)
		flow.save()
		return flow

	def test_a_sync_save_uploads_nothing(self):
		self.synced_flow()
		self.meta.add(FLOW_ID, "Deal feedback", flow_json=LEAD_QUALIFICATION)

		sync_flows(self.account)

		self.client.update_flow_json.assert_not_called()

	def test_a_user_edit_uploads_the_json_and_stores_meta_validation_errors(self):
		flow = self.synced_flow()
		error = validation_error("Missing required property 'children'")
		self.client.update_flow_json.return_value = flow_json_upload(error)

		self.edit(flow)

		self.client.update_flow_json.assert_called_once_with(FLOW_ID, json.dumps(LEAD_QUALIFICATION))
		flow.reload()
		self.assertEqual(json.loads(flow.validation_errors), [error])
		self.assertIn("QUALIFY", flow.get_outline().entry_screens)

	def test_an_upload_without_errors_clears_the_stored_ones(self):
		flow = self.synced_flow(validation_errors=[validation_error("Old error")])
		self.assertTrue(flow.validation_errors)

		self.edit(flow)

		self.assertFalse(flow.reload().validation_errors)

	def test_invalid_json_is_still_sent_to_meta(self):
		flow = self.synced_flow()

		self.edit(flow, "{not json")

		self.client.update_flow_json.assert_called_once_with(FLOW_ID, "{not json")
		self.assertEqual(flow.reload().get_outline().screens, [])

	def test_the_status_follows_meta_after_the_upload(self):
		flow = self.synced_flow(status="PUBLISHED")
		self.meta.flows[FLOW_ID]["status"] = "DRAFT"

		self.edit(flow)

		self.assertEqual(flow.reload().status, "Draft")

	def test_a_meta_error_blocks_the_save_with_its_message(self):
		flow = self.synced_flow(status="PUBLISHED")
		self.client.update_flow_json.side_effect = requests.HTTPError("Flow can't be updated")

		with self.assertRaisesRegex(frappe.ValidationError, "Flow can't be updated"):
			self.edit(flow)

		self.assertEqual(json.loads(frappe.db.get_value("WA Flow", FLOW_ID, "flow_json")), DEAL_FEEDBACK)

	def test_publish_is_refused_while_there_are_validation_errors(self):
		self.synced_flow(validation_errors=[validation_error("Missing required property 'children'")])

		with self.assertRaisesRegex(frappe.ValidationError, "validation errors"):
			publish_flow(FLOW_ID)

		self.client.publish_flow.assert_not_called()

	def test_publish_is_refused_outside_draft(self):
		self.synced_flow(status="PUBLISHED")

		with self.assertRaisesRegex(frappe.ValidationError, "Draft"):
			publish_flow(FLOW_ID)

		self.client.publish_flow.assert_not_called()

	def test_publishing_a_draft_refreshes_it_from_meta(self):
		self.synced_flow()
		self.client.publish_flow.side_effect = lambda flow_id: self.meta.flows[flow_id].update(
			status="PUBLISHED"
		)

		publish_flow(FLOW_ID)

		self.client.publish_flow.assert_called_once_with(FLOW_ID)
		self.assertEqual(frappe.db.get_value("WA Flow", FLOW_ID, "status"), "Published")

	def test_deprecate_is_refused_for_a_draft(self):
		self.synced_flow()

		with self.assertRaisesRegex(frappe.ValidationError, "Draft"):
			deprecate_flow(FLOW_ID)

		self.client.deprecate_flow.assert_not_called()

	def test_deprecating_a_published_flow_refreshes_it_from_meta(self):
		self.synced_flow(status="PUBLISHED")
		self.client.deprecate_flow.side_effect = lambda flow_id: self.meta.flows[flow_id].update(
			status="DEPRECATED"
		)

		deprecate_flow(FLOW_ID)

		self.client.deprecate_flow.assert_called_once_with(FLOW_ID)
		self.assertEqual(frappe.db.get_value("WA Flow", FLOW_ID, "status"), "Deprecated")

	def test_a_meta_error_on_an_action_is_shown_readably(self):
		self.synced_flow()
		self.client.publish_flow.side_effect = requests.HTTPError("Flow has validation errors on Meta")

		with self.assertRaisesRegex(frappe.ValidationError, "Flow has validation errors on Meta"):
			publish_flow(FLOW_ID)

	def test_refresh_fetches_a_fresh_preview_url(self):
		self.synced_flow()
		self.meta.flows[FLOW_ID]["preview"] = {
			"preview_url": "https://business.facebook.com/wa/manage/flows/7001/preview/?token=fresh",
			"expires_at": "2026-12-01T10:00:00+0000",
		}

		refresh_flow(FLOW_ID)

		self.assertTrue(frappe.db.get_value("WA Flow", FLOW_ID, "preview_url").endswith("token=fresh"))

	def test_a_user_without_write_on_flows_is_refused(self):
		self.synced_flow(status="PUBLISHED")

		with self.set_user("test1@example.com"):
			for action in (publish_flow, deprecate_flow, refresh_flow):
				with self.subTest(action=action.__name__), self.assertRaises(frappe.PermissionError):
					action(FLOW_ID)

		self.client.deprecate_flow.assert_not_called()
