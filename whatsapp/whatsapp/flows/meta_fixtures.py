# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

# Graph API responses and webhook values shaped after Meta's Flows docs. Replace with captured ones when available.

import json
import secrets
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.flows.flow_json_fixtures import DEAL_FEEDBACK

CLIENT = "whatsapp.whatsapp.doctype.wa_template.wa_template.WhatsApp"


def flow_row(flow_id: str, name: str, status: str = "DRAFT") -> dict:
	return {
		"id": flow_id,
		"name": name,
		"status": status,
		"categories": ["LEAD_GENERATION"],
		"validation_errors": [],
	}


def flow_list(*rows: dict, after: str | None = None) -> dict:
	page = {
		"data": list(rows),
		"paging": {"cursors": {"before": "QVFI_before", "after": after or "QVFI_last"}},
	}
	if after:
		page["paging"]["next"] = f"https://graph.facebook.com/v23.0/biz/flows?after={after}"
	return page


def flow_details(flow_id: str, name: str, status: str = "PUBLISHED", **overrides) -> dict:
	return {
		"id": flow_id,
		"name": name,
		"status": status,
		"categories": ["LEAD_GENERATION", "SURVEY"],
		"validation_errors": [],
		"json_version": "7.3",
		"endpoint_uri": "https://example.com/flow-endpoint",
		"preview": {
			"preview_url": f"https://business.facebook.com/wa/manage/flows/{flow_id}/preview/?token=abc",
			"expires_at": "2026-05-21T11:18:09+0000",
		},
		**overrides,
	}


def flow_assets(download_url: str) -> dict:
	return {
		"data": [{"name": "flow.json", "asset_type": "FLOW_JSON", "download_url": download_url}],
		"paging": {"cursors": {"before": "QVFI_before", "after": "QVFI_after"}},
	}


def webhook_payload(business_id: str, value: dict) -> dict:
	return {
		"entry": [{"id": business_id, "time": 1684969340, "changes": [{"value": value, "field": "flows"}]}],
		"object": "whatsapp_business_account",
	}


def status_change(flow_id: str, new_status: str, old_status: str | None = "DRAFT") -> dict:
	value = {
		"event": "FLOW_STATUS_CHANGE",
		"message": f"Flow Webhook 3 changed status from {old_status} to {new_status}",
		"flow_id": flow_id,
		"new_status": new_status,
	}
	if old_status:
		value["old_status"] = old_status
	return value


def endpoint_error_rate(flow_id: str, alert_state: str = "ACTIVATED") -> dict:
	return {
		"event": "ENDPOINT_ERROR_RATE",
		"message": "Flow Webhook 3's endpoint error rate has reached the 10% threshold.",
		"flow_id": flow_id,
		"error_rate": 30,
		"threshold": 10,
		"alert_state": alert_state,
		"errors": [
			{"error_type": "INVALID_SCREEN_TRANSITION", "error_count": 2, "error_rate": 50},
			{"error_type": "public-key-missing", "error_count": 2, "error_rate": 50},
		],
	}


def version_expiry_warning(flow_id: str) -> dict:
	return {
		"event": "FLOW_VERSION_EXPIRY_WARNING",
		"message": "Flow Webhook 3 uses a Flow JSON version that expires soon.",
		"flow_id": flow_id,
		"warning": "Flow JSON version 3.0 will expire on 2026-12-01. Update the Flow JSON version.",
	}


def nfm_reply(sender: str, response: dict | str, context_id: str | None = None, body: str = "Sent") -> dict:
	"""An incoming completed Flow, as an entry of a `messages` webhook value's `messages`."""
	message = {
		"from": sender,
		"id": f"wamid.{secrets.token_hex(8)}",
		"type": "interactive",
		"timestamp": "1700000000",
		"interactive": {
			"type": "nfm_reply",
			"nfm_reply": {
				"name": "flow",
				"body": body,
				"response_json": response if isinstance(response, str) else json.dumps(response),
			},
		},
	}
	if context_id:
		message["context"] = {"from": "16315558151", "id": context_id}
	return message


def messages_payload(phone_number_id: str, message: dict, profile_name: str = "Asha") -> dict:
	value = {
		"messaging_product": "whatsapp",
		"metadata": {"display_phone_number": "16315558151", "phone_number_id": phone_number_id},
		"contacts": [{"profile": {"name": profile_name}, "wa_id": message["from"]}],
		"messages": [message],
	}
	return {
		"object": "whatsapp_business_account",
		"entry": [{"id": "102290129340398", "changes": [{"value": value, "field": "messages"}]}],
	}


def validation_error(message: str, line: int = 12, column: int = 4, path: str = "screens[0].layout") -> dict:
	return {
		"error": "INVALID_PROPERTY_VALUE",
		"error_type": "FLOW_JSON_ERROR",
		"message": message,
		"line_start": line,
		"line_end": line,
		"column_start": column,
		"column_end": column + 10,
		"pointers": [
			{
				"line_start": line,
				"line_end": line,
				"column_start": column,
				"column_end": column + 10,
				"path": path,
			}
		],
	}


def flow_json_upload(*errors: dict) -> dict:
	return {"success": True, "validation_errors": list(errors)}


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
		self.client.create_template.side_effect = lambda payload: {
			"id": frappe.generate_hash(length=10),
			"status": "PENDING",
		}

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


def business_id(account_name: str) -> str:
	return frappe.db.get_value("WA Account", account_name, "business_id")


class FlowMetaCase(IntegrationTestCase):
	"""An Administrator with a fresh WA Account whose Graph client is `self.meta`."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.account = make_account()
		self.meta = FakeMeta()
		self.client = self.meta.client
		self.start_patch(CLIENT, return_value=self.client)

	def start_patch(self, target: str, **kwargs) -> MagicMock:
		patcher = patch(target, **kwargs)
		self.addCleanup(patcher.stop)
		return patcher.start()
