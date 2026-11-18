# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests import IntegrationTestCase
from frappe.utils import convert_utc_to_system_timezone

from whatsapp.whatsapp.flows.flow_json_fixtures import DEAL_FEEDBACK, LEAD_QUALIFICATION
from whatsapp.whatsapp.flows.meta_fixtures import flow_assets, flow_details, flow_row
from whatsapp.whatsapp.flows.sync import sync_active_accounts, sync_flows
from whatsapp.whatsapp.flows.template_fixtures import flow_button, template_doc

CLIENT = "whatsapp.whatsapp.doctype.wa_template.wa_template.WhatsApp"


class FakeMeta:
	"""Flows one business account holds on Meta, served through a mocked Graph client."""

	def __init__(self):
		self.flows = {}
		self.flow_json = {}
		self.client = MagicMock()
		self.client.get_flows.side_effect = lambda: [
			flow_row(flow_id, details["name"], details["status"]) for flow_id, details in self.flows.items()
		]
		self.client.get_flow.side_effect = lambda flow_id: self.flows[flow_id]
		self.client.get_flow_assets.side_effect = lambda flow_id: flow_assets(
			f"https://cdn.example/{flow_id}"
		)
		self.client.download_flow_json.side_effect = lambda url: self.flow_json[url.rsplit("/", 1)[-1]]

	def add(self, flow_id: str, name: str, flow_json: dict | str = DEAL_FEEDBACK, **details) -> None:
		self.flows[flow_id] = flow_details(flow_id, name, **details)
		self.flow_json[flow_id] = flow_json if isinstance(flow_json, str) else json.dumps(flow_json)


def make_account(business_id: str | None = None, status: str = "Active") -> str:
	uid = frappe.generate_hash(length=6)
	return (
		frappe.get_doc(
			doctype="WA Account",
			account_name=f"_Test Flow Acc {uid}",
			status=status,
			phone_id=f"phone_{uid}",
			business_id=business_id or f"biz_{uid}",
			app_id="test_app",
			access_token="test_token",
		)
		.insert()
		.name
	)


def logs_for(flow_name: str, level: str) -> list[str]:
	return frappe.get_all(
		"WA Log",
		filters={"reference_doctype": "WA Flow", "reference_docname": flow_name, "level": level},
		pluck="message",
	)


class IntegrationTestFlowSync(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.account = make_account()
		self.meta = FakeMeta()
		patcher = patch(CLIENT, return_value=self.meta.client)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_sync_creates_a_flow_with_every_field_from_meta(self):
		self.meta.add("1001", "Deal feedback", status="PUBLISHED")

		counts = sync_flows(self.account)

		self.assertEqual(counts, {"created": 1, "updated": 0, "removed": 0})
		flow = frappe.get_doc("WA Flow", "1001")
		self.assertEqual(flow.flow_name, "Deal feedback")
		self.assertEqual(flow.whatsapp_account, self.account)
		self.assertEqual(flow.status, "Published")
		self.assertEqual(flow.categories, "LEAD_GENERATION, SURVEY")
		self.assertEqual(flow.json_version, "7.3")
		self.assertEqual(flow.endpoint_uri, "https://example.com/flow-endpoint")
		self.assertEqual(json.loads(flow.flow_json), DEAL_FEEDBACK)
		self.assertTrue(flow.preview_url.startswith("https://business.facebook.com/wa/manage/flows/1001"))
		self.assertEqual(
			flow.preview_expires_at,
			convert_utc_to_system_timezone(datetime(2026, 5, 21, 11, 18, 9)).replace(tzinfo=None),
		)

	def test_the_outline_of_the_downloaded_flow_json_is_stored(self):
		self.meta.add("1002", "Lead qualification", flow_json=LEAD_QUALIFICATION)

		sync_flows(self.account)

		outline = frappe.get_doc("WA Flow", "1002").get_outline()
		self.assertEqual(outline.entry_screens, {"QUALIFY": {"lead_name": "string"}})
		self.assertEqual(outline.sensitive, ["budget", "passcode"])

	def test_a_flow_with_invalid_json_is_still_synced_with_an_empty_outline(self):
		self.meta.add("1003", "Half-built draft", flow_json="{not json", status="DRAFT")

		sync_flows(self.account)

		flow = frappe.get_doc("WA Flow", "1003")
		self.assertEqual(flow.flow_json, "{not json")
		self.assertEqual(flow.status, "Draft")
		self.assertEqual(flow.get_outline().answers, [])
		self.assertTrue(logs_for(flow.name, level="Warning"))

	def test_a_second_sync_updates_listed_flows_and_removes_unlisted_ones(self):
		self.meta.add("1004", "Feedback", status="DRAFT")
		self.meta.add("1005", "Old survey")
		sync_flows(self.account)
		self.meta.add("1004", "Feedback v2", status="PUBLISHED")
		del self.meta.flows["1005"]

		counts = sync_flows(self.account)

		self.assertEqual(counts, {"created": 0, "updated": 1, "removed": 1})
		flow = frappe.get_doc("WA Flow", "1004")
		self.assertEqual((flow.flow_name, flow.status), ("Feedback v2", "Published"))
		self.assertFalse(frappe.db.exists("WA Flow", "1005"))

	def test_flows_of_other_accounts_are_not_removed(self):
		other_account = make_account()
		frappe.get_doc(doctype="WA Flow", flow_id="1006", whatsapp_account=other_account).insert()

		sync_flows(self.account)

		self.assertTrue(frappe.db.exists("WA Flow", "1006"))

	def test_accounts_of_one_business_share_its_flows(self):
		business_id = frappe.db.get_value("WA Account", self.account, "business_id")
		other_number = make_account(business_id=business_id)
		self.meta.add("1010", "Deal feedback")
		self.meta.client.create_template.side_effect = lambda payload: {
			"id": frappe.generate_hash(length=10),
			"status": "PENDING",
		}

		sync_flows(self.account)
		sync_flows(other_number)
		template_doc(other_number, [flow_button("1010")]).insert()
		template_doc(self.account, [flow_button("1010")]).insert()

		flow = frappe.get_doc("WA Flow", "1010")
		self.assertEqual((flow.whatsapp_account, flow.business_id), (self.account, business_id))

	def test_an_existing_flow_is_locked_before_meta_is_asked_for_it(self):
		self.meta.add("1011", "Feedback", status="DRAFT")
		sync_flows(self.account)
		queries = []
		original_sql = frappe.db.__class__.sql

		def recording_sql(db, query, *args, **kwargs):
			queries.append(str(query))
			return original_sql(db, query, *args, **kwargs)

		def locked_when_fetched(flow_id):
			locks = [q for q in queries if "tabWA Flow" in q and "for update" in q.lower()]
			self.assertTrue(locks, "Meta was asked for the Flow before its row was locked")
			return self.meta.flows[flow_id]

		self.meta.client.get_flow.side_effect = locked_when_fetched
		with patch.object(frappe.db.__class__, "sql", recording_sql):
			sync_flows(self.account)

	def test_a_failed_download_keeps_the_previous_flow_json_and_syncs_the_other_flows(self):
		self.meta.add("1007", "Feedback")
		self.meta.add("1008", "Survey")
		sync_flows(self.account)
		self.meta.add("1007", "Feedback", flow_json=LEAD_QUALIFICATION)
		self.meta.add("1008", "Survey v2")
		self.meta.client.download_flow_json.side_effect = self._fail_for("1007")

		sync_flows(self.account)

		self.assertEqual(json.loads(frappe.db.get_value("WA Flow", "1007", "flow_json")), DEAL_FEEDBACK)
		self.assertEqual(frappe.db.get_value("WA Flow", "1008", "flow_name"), "Survey v2")
		self.assertTrue(
			frappe.db.exists(
				"WA Log", {"level": "Error", "event_type": "Flow", "message": ("like", "%1007%")}
			)
		)

	def test_a_removed_flow_takes_its_logs_with_it(self):
		self.meta.add("1009", "Old survey")
		sync_flows(self.account)
		del self.meta.flows["1009"]

		sync_flows(self.account)

		self.assertFalse(frappe.db.exists("WA Flow", "1009"))
		self.assertFalse(logs_for("1009", level="Info"))

	def test_a_removed_flow_that_a_template_button_links_to_is_kept(self):
		self.meta.add("1010", "Feedback")
		sync_flows(self.account)
		template = template_doc(self.account, [flow_button("1010")], template_name="_test_kept_flow")
		template.flags.from_sync = True
		template.insert()
		del self.meta.flows["1010"]

		counts = sync_flows(self.account)

		self.assertEqual(counts["removed"], 0)
		self.assertTrue(frappe.db.exists("WA Flow", "1010"))
		self.assertTrue(logs_for("1010", level="Info"))
		self.assertTrue(logs_for("1010", level="Warning"))

	def test_an_unknown_meta_status_keeps_the_current_status(self):
		self.meta.add("1011", "Feedback", status="PUBLISHED")
		self.meta.add("1012", "Survey", status="DRAFT")
		sync_flows(self.account)
		self.meta.add("1011", "Feedback", status="PAUSED")
		self.meta.add("1012", "Survey", status="PUBLISHED")

		sync_flows(self.account)

		self.assertEqual(frappe.db.get_value("WA Flow", "1011", "status"), "Published")
		self.assertEqual(frappe.db.get_value("WA Flow", "1012", "status"), "Published")
		self.assertTrue(logs_for("1011", level="Warning"))

	def _fail_for(self, flow_id: str):
		def download(url: str) -> str:
			if url.endswith(flow_id):
				raise requests.HTTPError("403 Forbidden")
			return self.meta.flow_json[url.rsplit("/", 1)[-1]]

		return download


class IntegrationTestDailyFlowSync(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.clients = {}
		patcher = patch(
			CLIENT, side_effect=lambda args: self.clients.get(args.business_id, FakeMeta()).client
		)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_one_failing_account_does_not_stop_the_others(self):
		failing, healthy = make_account(), make_account()
		self.clients[business_id(failing)] = FakeMeta()
		self.clients[business_id(failing)].add("2001", "Synced before the failure")
		self.clients[business_id(failing)].client.get_flow.side_effect = [
			flow_details("2001", "Synced before the failure"),
			requests.HTTPError("500 Internal Server Error"),
		]
		self.clients[business_id(failing)].add("2002", "Fails")
		self.clients[business_id(healthy)] = FakeMeta()
		self.clients[business_id(healthy)].add("2003", "Healthy")

		sync_active_accounts()

		self.assertFalse(frappe.db.exists("WA Flow", "2001"))
		self.assertTrue(frappe.db.exists("WA Flow", "2003"))
		self.assertTrue(frappe.db.exists("WA Log", {"level": "Error", "account": failing}))

	def test_inactive_accounts_are_skipped(self):
		inactive = make_account(status="Inactive")
		self.clients[business_id(inactive)] = FakeMeta()
		self.clients[business_id(inactive)].add("2004", "Never synced")

		sync_active_accounts()

		self.assertFalse(frappe.db.exists("WA Flow", "2004"))


def business_id(account_name: str) -> str:
	return frappe.db.get_value("WA Account", account_name, "business_id")
