# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

"""The Flow parts of an outgoing message: its token, a template's Flow button components and the interactive Flow message.

No live Meta account has confirmed these shapes yet, so each unverified choice is its own constant or function.
"""

import json
from functools import cached_property

import frappe
from frappe import _
from frappe.utils import cint, flt

from whatsapp.whatsapp.flows.token import FlowToken

FLOW_BUTTON_SUB_TYPE = "flow"
FLOW_MESSAGE_VERSION = "3"
UNSENDABLE_STATUSES = ("Blocked", "Deprecated")
SEND_MODES = ("published", "draft")


def assign_flow_token(message) -> None:
	if not message.flow_token and (message.flow or _flow_buttons(message)):
		message.flow_token = FlowToken.new().base


def validate_sendable_flows(message) -> None:
	"""Throw before Meta is called when a Flow the message opens is Blocked or Deprecated."""
	if message.is_template:
		flows = [button.flow for _index, button in _flow_buttons(message)]
	else:
		flows = [message.flow]
	for flow in filter(None, flows):
		_refuse_unsendable(frappe.db.get_value("WA Flow", flow, ["flow_name", "status"], as_dict=True))


def validate_flow_inputs_reference(message, template) -> None:
	"""Flow inputs name fields of the template's reference DocType, so only its documents can fill them."""
	reference_doctype = message.reference_doctype if message.reference_docname else None
	if _has_flow_inputs(template) and template.reference_doctype != reference_doctype:
		frappe.throw(
			_("Template '{0}' fills Flow inputs from {1}; cannot send from {2}.").format(
				template.name, template.reference_doctype, reference_doctype or _("no reference document")
			)
		)


def validate_update_reference_permission(message, template) -> None:
	"""Update Reference actions save the reference without permission checks, so the sender must be able to write it."""
	if not _has_update_reference(template):
		return
	reference_doctype = message.reference_doctype if message.reference_docname else None
	if template.reference_doctype != reference_doctype:
		frappe.throw(
			_("Template '{0}' updates {1} from Flow responses; cannot send from {2}.").format(
				template.name, template.reference_doctype, reference_doctype or _("no reference document")
			)
		)
	if not frappe.has_permission(reference_doctype, "write", doc=message.reference_docname):
		frappe.throw(
			_(
				"Template '{0}' updates {1} {2} from Flow responses, and you have no write permission on it."
			).format(template.name, reference_doctype, message.reference_docname),
			frappe.PermissionError,
		)


def flow_button_components(message, template) -> list[dict]:
	"""One button component per Flow button, with the message's token and the button's resolved Flow inputs."""
	token = FlowToken(message.flow_token)
	inputs = FlowInputs(message)
	return [
		_button_component(index, token.for_button(index, button.flow), inputs.resolve(button))
		for index, button in template_flow_buttons(template)
	]


def template_flow_buttons(template) -> list[tuple[int, object]]:
	"""Flow buttons with their index among all the template's buttons, which is the index Meta sends them by."""
	return [
		(index, button)
		for index, button in enumerate(template.get("buttons") or [])
		if button.button_type == "Flow"
	]


def interactive_flow_screen(flow_name: str, screen: str | None, mode: str) -> str:
	"""Check an interactive Flow send, and return the screen it opens on."""
	if mode not in SEND_MODES:
		frappe.throw(_("Mode must be one of: {0}").format(", ".join(SEND_MODES)))

	flow = frappe.get_doc("WA Flow", flow_name)
	flow.check_permission("write" if mode == "draft" else "read")
	_refuse_unsendable(flow)
	if flow.status == "Draft" and mode != "draft":
		frappe.throw(
			_('Flow {0} is a Draft. Publish it, or send it with mode "draft" to test it.').format(
				flow.flow_name
			)
		)

	entry_screens = flow.get_outline().entry_screens
	if not entry_screens:
		return screen or ""
	if not screen:
		return next(iter(entry_screens))
	if screen not in entry_screens:
		frappe.throw(
			_("{0} is not an entry screen of Flow {1}. Choose one of: {2}").format(
				screen, flow.flow_name, ", ".join(entry_screens)
			)
		)
	return screen


def parse_flow_data(data: str | None) -> dict | None:
	if not data:
		return None
	try:
		parsed = json.loads(data)
	except ValueError:
		parsed = None
	if not isinstance(parsed, dict):
		frappe.throw(_("Flow data must be a JSON object"))
	return parsed


def interactive_flow_payload(message, to: str) -> dict:
	parameters = {
		"flow_message_version": FLOW_MESSAGE_VERSION,
		"flow_token": message.flow_token,
		"flow_id": frappe.db.get_value("WA Flow", message.flow, "flow_id"),
		"flow_cta": message.flow_cta,
		"flow_action": "navigate",
		"flow_action_payload": _action_payload(message),
		**({"mode": "draft"} if message.flow_mode == "Draft" else {}),
	}
	interactive = {
		"type": "flow",
		"body": {"text": message.message or ""},
		"action": {"name": "flow", "parameters": parameters},
	}
	return {
		"messaging_product": "whatsapp",
		"recipient_type": "individual",
		"to": to,
		"type": "interactive",
		"interactive": interactive,
	}


class FlowInputs:
	"""A template's Flow inputs, resolved from the message's reference document."""

	def __init__(self, message):
		self.message = message

	def resolve(self, button) -> dict:
		rows = frappe.parse_json(button.flow_inputs) or []
		if not rows:
			return {}
		declared = (
			frappe.get_doc("WA Flow", button.flow).get_outline().entry_screens.get(button.flow_screen, {})
		)
		data = {}
		for row in rows:
			value = self.reference.get(row["source_field"])
			# Flows reject null, so an empty value is left out.
			if value is None or value == "":
				continue
			data[row["key"]] = CONVERTERS.get(declared.get(row["key"]), str)(value)
		return data

	@cached_property
	def reference(self):
		return frappe.get_doc(self.message.reference_doctype, self.message.reference_docname)


def _has_flow_inputs(template) -> bool:
	return any(frappe.parse_json(button.flow_inputs) for _index, button in template_flow_buttons(template))


def _has_update_reference(template) -> bool:
	return any(
		action.get("action") == "Update Reference"
		for _index, button in template_flow_buttons(template)
		for action in frappe.parse_json(button.flow_response_actions) or []
	)


def _flow_buttons(message) -> list[tuple[int, object]]:
	if not (message.is_template and message.whatsapp_template):
		return []
	return template_flow_buttons(frappe.get_cached_doc("WA Template", message.whatsapp_template))


def _refuse_unsendable(flow) -> None:
	if flow.status in UNSENDABLE_STATUSES:
		frappe.throw(_("Flow {0} is {1} on Meta, so it cannot be sent").format(flow.flow_name, flow.status))


def _button_component(index: int, token: FlowToken, data: dict) -> dict:
	action = {"flow_token": str(token), **({"flow_action_data": data} if data else {})}
	return {
		"type": "button",
		"sub_type": FLOW_BUTTON_SUB_TYPE,
		"index": _button_index(index),
		"parameters": [{"type": "action", "action": action}],
	}


def _button_index(index: int) -> str:
	"""Meta's docs send the index as a string; the pywa SDK sends an integer."""
	return str(index)


def _action_payload(message) -> dict:
	data = frappe.parse_json(message.flow_action_data) if message.flow_action_data else None
	return {
		**({"screen": message.flow_screen} if message.flow_screen else {}),
		**({"data": _interactive_data(data)} if data else {}),
	}


def _interactive_data(data: dict) -> str:
	"""Meta's docs give an interactive message's data as a JSON object serialized to a string,
	while a template's flow_action_data is an object."""
	return json.dumps(data)


def _number(value) -> int | float:
	number = flt(value)
	return int(number) if number.is_integer() else number


CONVERTERS = {"string": str, "number": _number, "boolean": lambda value: bool(cint(value))}
