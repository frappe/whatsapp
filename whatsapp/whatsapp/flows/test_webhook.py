# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
from unittest.mock import MagicMock, call, patch

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.flows.meta_fixtures import (
	FlowMetaCase,
	business_id,
	endpoint_error_rate,
	status_change,
	version_expiry_warning,
	webhook_payload,
)
from whatsapp.whatsapp.webhook import handler

NOTIFY = "whatsapp.whatsapp.doctype.wa_flow.wa_flow.WAFlow.run_notifications"


class IntegrationTestFlowWebhook(FlowMetaCase):
	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("WA Settings", "webhook_secret", "")
		self.business_id = business_id(self.account)
		self.notify = self.start_patch(NOTIFY)

	def deliver(self, value: dict, business_id: str | None = None) -> str:
		frappe.local.form_dict = frappe._dict(webhook_payload(business_id or self.business_id, value))
		frappe.local.request = MagicMock(method="POST")
		self.addCleanup(
			lambda: delattr(frappe.local, "request") if hasattr(frappe.local, "request") else None
		)
		return handler()

	def make_flow(self, flow_id: str, status: str = "Draft") -> None:
		frappe.get_doc(
			doctype="WA Flow", flow_id=flow_id, flow_name="Deal feedback", whatsapp_account=self.account
		).insert()
		frappe.db.set_value("WA Flow", flow_id, "status", status)
		self.notify.reset_mock()

	def flow_logs(self, flow_id: str) -> list[dict]:
		return frappe.get_all(
			"WA Log",
			filters={"reference_doctype": "WA Flow", "reference_docname": flow_id, "event_type": "Flow"},
			fields=["level", "message", "response_data"],
			order_by="creation desc",
		)

	def test_a_status_change_updates_a_known_flow(self):
		self.make_flow("3001")

		self.assertEqual(self.deliver(status_change("3001", "PUBLISHED")), "ok")

		self.assertEqual(frappe.db.get_value("WA Flow", "3001", "status"), "Published")
		self.notify.assert_called_once_with("on_flow_status_change")

	def test_a_flow_that_becomes_throttled_or_blocked_raises_an_alert(self):
		for flow_id, status in (("3008", "THROTTLED"), ("3009", "BLOCKED")):
			self.make_flow(flow_id, status="Published")

			self.deliver(status_change(flow_id, status))

			self.assertEqual(
				self.notify.call_args_list, [call("on_flow_status_change"), call("on_flow_alert")]
			)

	def test_a_failing_event_leaves_no_partial_flow(self):
		self.meta.add("3010", "Created on Meta", status="DRAFT")
		fail_after_the_flow_is_saved = patch(
			"whatsapp.whatsapp.doctype.wa_flow.wa_flow.WAFlow.log",
			side_effect=frappe.ValidationError("log failed"),
		)

		with fail_after_the_flow_is_saved:
			self.assertEqual(self.deliver(status_change("3010", "DRAFT", old_status=None)), "ok")

		self.assertFalse(frappe.db.exists("WA Flow", "3010"))
		self.assertTrue(
			frappe.db.exists("WA Log", {"level": "Error", "message": ("like", "%FLOW_STATUS_CHANGE%")})
		)

	def test_an_unknown_status_keeps_the_current_one_with_a_warning(self):
		self.make_flow("3007", status="Published")

		self.deliver(status_change("3007", "PAUSED"))

		self.assertEqual(frappe.db.get_value("WA Flow", "3007", "status"), "Published")
		self.assertEqual([entry.level for entry in self.flow_logs("3007")], ["Warning"])
		self.notify.assert_not_called()

	def test_the_creation_event_syncs_the_unknown_flow(self):
		self.meta.add("3002", "Created on Meta", status="DRAFT")

		self.deliver(status_change("3002", "DRAFT", old_status=None))

		self.assertEqual(frappe.db.get_value("WA Flow", "3002", "whatsapp_account"), self.account)

	def test_an_activated_alert_is_logged_with_normalised_error_types_and_notified(self):
		self.make_flow("3003", status="Published")

		self.deliver(endpoint_error_rate("3003", "ACTIVATED"))

		entry = self.flow_logs("3003")[0]
		self.assertEqual(entry.level, "Warning")
		self.assertEqual(
			[error["error_type"] for error in json.loads(entry.response_data)["errors"]],
			["invalid_screen_transition", "public_key_missing"],
		)
		self.notify.assert_called_once_with("on_flow_alert")

	def test_a_deactivated_alert_is_logged_as_info_without_a_notification(self):
		self.make_flow("3004", status="Published")

		self.deliver(endpoint_error_rate("3004", "DEACTIVATED"))

		self.assertEqual(self.flow_logs("3004")[0].level, "Info")
		self.notify.assert_not_called()

	def test_a_version_expiry_warning_is_logged_and_notified(self):
		self.make_flow("3005", status="Published")

		self.deliver(version_expiry_warning("3005"))

		entry = self.flow_logs("3005")[0]
		self.assertEqual(entry.level, "Warning")
		self.assertIn("will expire", entry.message)
		self.notify.assert_called_once_with("on_flow_alert")

	def test_an_event_for_an_unknown_account_is_logged_and_still_answered(self):
		self.assertEqual(self.deliver(status_change("3006", "DRAFT", old_status=None), "unknown_waba"), "ok")
		self.assertEqual(self.deliver(endpoint_error_rate("3006"), "unknown_waba"), "ok")

		self.assertFalse(frappe.db.exists("WA Flow", "3006"))
		self.assertEqual(
			frappe.db.count(
				"WA Log", {"level": "Warning", "event_type": "Flow", "message": ("like", "%3006%")}
			),
			2,
		)
		self.meta.client.get_flow.assert_not_called()
