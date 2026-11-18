# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

"""A template's Flow button as Meta spells it, in both directions.

The live probe has not run (SPEC.md, "Gate"), so each unverified choice is its own constant or function.
"""

import frappe

SENDABLE_FIELDS = ("flow", "flow_screen", "flow_icon", "flow_action")

FLOW_ACTIONS = {"navigate": "Navigate", "data_exchange": "Data Exchange"}

# From Meta's changelog and the pywa SDK; absent from Meta's API reference.
FLOW_ICONS = {"DOCUMENT": "Document", "PROMOTION": "Promotion", "REVIEW": "Review"}


def flow_button_payload(button) -> dict:
	"""Meta's FLOW button for a WA Template Button row of type Flow."""
	return {
		"type": "FLOW",
		"text": button.button_text,
		"flow_id": button.flow,
		"flow_action": _api_value(FLOW_ACTIONS, button.flow_action or "Navigate"),
		**_navigate_screen(button),
		**_icon(button),
	}


def flow_button_row(meta_button: dict) -> dict:
	"""A WA Template Button row from Meta's FLOW button. `flow` holds Meta's Flow ID, which names the WA Flow."""
	return {
		"button_type": "Flow",
		"button_text": meta_button.get("text"),
		"flow": meta_button.get("flow_id"),
		"flow_screen": meta_button.get("navigate_screen") or "",
		"flow_action": FLOW_ACTIONS.get(meta_button.get("flow_action") or "", "Navigate"),
		"flow_icon": FLOW_ICONS.get(meta_button.get("icon") or "", ""),
	}


def add_flow_details(buttons: list[dict]) -> None:
	"""Add the name and status of each button's Flow, for a picker that sends templates."""
	names = list({button["flow"] for button in buttons if button.get("flow")})
	flows = (
		{
			flow.name: flow
			for flow in frappe.get_all(
				"WA Flow", filters={"name": ["in", names]}, fields=["name", "flow_name", "status"]
			)
		}
		if names
		else {}
	)
	for button in buttons:
		flow = flows.get(button.get("flow")) or {}
		button["flow_name"] = flow.get("flow_name")
		button["flow_status"] = flow.get("status")


def _navigate_screen(button) -> dict:
	"""Meta's docs call navigate_screen both required and optional, so it is sent only when set."""
	return {"navigate_screen": button.flow_screen} if button.flow_screen else {}


def _icon(button) -> dict:
	return {"icon": _api_value(FLOW_ICONS, button.flow_icon)} if button.flow_icon else {}


def _api_value(mapping: dict[str, str], local_value: str) -> str:
	return next(api_value for api_value, local in mapping.items() if local == local_value)
