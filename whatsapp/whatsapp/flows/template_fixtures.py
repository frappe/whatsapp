# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

# Meta template payloads shaped after Meta's flows-templates guide. Replace with captured ones when available.

import json

import frappe

from whatsapp.whatsapp.doctype.wa_template.wa_template import _ensure_language
from whatsapp.whatsapp.flows.flow_json_fixtures import DEAL_FEEDBACK


def make_flow(account: str, flow_id: str, flow_json: dict | str = DEAL_FEEDBACK, status: str = "Published"):
	return frappe.get_doc(
		doctype="WA Flow",
		flow_id=flow_id,
		flow_name=f"Flow {flow_id}",
		whatsapp_account=account,
		business_id=frappe.db.get_value("WA Account", account, "business_id"),
		status=status,
		flow_json=flow_json if isinstance(flow_json, str) else json.dumps(flow_json),
	).insert()


def flow_button(flow: str, text: str = "Give feedback", **fields) -> dict:
	for key in ("flow_inputs", "flow_response_actions"):
		if key in fields and not isinstance(fields[key], str):
			fields[key] = json.dumps(fields[key])
	return {"button_type": "Flow", "button_text": text, "flow": flow, **fields}


def template_doc(account: str, buttons: list[dict], reference_doctype: str | None = "Contact", **fields):
	_ensure_language("en_US")
	uid = frappe.generate_hash(length=6)
	return frappe.get_doc(
		doctype="WA Template",
		template_label=f"_Test Flow Template {uid}",
		template_type="Utility",
		language="en_US",
		message="How did we do?",
		whatsapp_account=account,
		reference_doctype=reference_doctype,
		buttons=buttons,
		**fields,
	)


def meta_flow_button(flow_id: str, text: str = "Give feedback", **fields) -> dict:
	return {"type": "FLOW", "text": text, "flow_id": flow_id, **fields}


def meta_template(template_id: str, name: str, buttons: list[dict]) -> dict:
	return {
		"id": template_id,
		"name": name,
		"category": "UTILITY",
		"language": "en_US",
		"status": "APPROVED",
		"components": [
			{"type": "BODY", "text": "How did we do?"},
			{"type": "BUTTONS", "buttons": buttons},
		],
	}
