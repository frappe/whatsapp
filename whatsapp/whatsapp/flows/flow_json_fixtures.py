# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
from pathlib import Path

# Flow JSON shaped after Meta's Flow JSON reference (version 7.x). Replace with real Flows when available.
FLOW_JSON = Path(__file__).parent / "flow_json"


def complete(payload: dict) -> dict:
	return {"name": "complete", "payload": payload}


def footer(label: str, action: dict) -> dict:
	return {"type": "Footer", "label": label, "on-click-action": action}


def screen(screen_id: str, children: list, **properties) -> dict:
	return {
		"id": screen_id,
		"title": screen_id.title(),
		**properties,
		"layout": {"type": "SingleColumnLayout", "children": children},
	}


def load(group: str, name: str) -> dict:
	return json.loads((FLOW_JSON / group / f"{name}.json").read_text())


DEAL_FEEDBACK = load("ours", "deal_feedback")
LEAD_QUALIFICATION = load("ours", "lead_qualification")
CUSTOMER_PROFILE = load("ours", "customer_profile")
CYCLIC = load("ours", "cyclic")
ROUTED = load("ours", "routed")
PREFILLED = load("ours", "prefilled")
