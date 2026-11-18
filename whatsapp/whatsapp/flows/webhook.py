# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.core.doctype.server_script.server_script_utils import run_server_script_for_doc_event

from whatsapp.whatsapp.api.utils import log
from whatsapp.whatsapp.flows.sync import known_status, sync_flow

ALERT_EVENTS = frozenset(
	{"ENDPOINT_ERROR_RATE", "ENDPOINT_LATENCY", "ENDPOINT_AVAILABILITY", "CLIENT_ERROR_RATE"}
)
ALERT_STATUSES = frozenset({"Throttled", "Blocked"})


def handle_flow_event(business_id: str, value: dict) -> None:
	"""Handle one change of the `flows` webhook field. Never raises, so Meta still gets its 200."""
	event = value.get("event")
	savepoint = f"flow_event_{frappe.generate_hash(length=8)}"
	frappe.db.savepoint(savepoint)
	try:
		if event == "FLOW_STATUS_CHANGE":
			_handle_status_change(business_id, value)
		elif event in ALERT_EVENTS:
			_handle_alert(business_id, value)
		elif event == "FLOW_VERSION_EXPIRY_WARNING":
			_handle_expiry_warning(business_id, value)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		log("Error", "Flow", f"Could not handle the Flow webhook event {event}", response_data=value)


def _handle_status_change(business_id: str, value: dict) -> None:
	flow_id = value.get("flow_id")
	if frappe.db.exists("WA Flow", flow_id):
		_update_status(frappe.get_doc("WA Flow", flow_id), value)
		return

	account = _account_for(business_id, value)
	if account:
		sync_flow(account, flow_id)


def _update_status(doc, value: dict) -> None:
	old_status = doc.status
	new_status = known_status(value.get("new_status"), doc)
	if old_status == new_status:
		return

	frappe.db.set_value("WA Flow", doc.name, "status", new_status)
	doc.status = new_status
	doc.run_notifications("on_flow_status_change")
	if new_status in ALERT_STATUSES:
		doc.run_notifications("on_flow_alert")
	run_server_script_for_doc_event(doc, "on_update")
	doc.log("Info", f"Flow {doc.flow_name} status changed: {old_status} -> {new_status}", response_data=value)


def _handle_alert(business_id: str, value: dict) -> None:
	doc = _flow_for(business_id, value)
	if not doc:
		return

	activated = value.get("alert_state") == "ACTIVATED"
	value = {**value, "errors": [_normalise_error(error) for error in value.get("errors", [])]}
	doc.log(
		"Warning" if activated else "Info",
		f"Flow {doc.flow_name}: {value['event']} {value.get('alert_state')}. {value.get('message', '')}",
		response_data=value,
	)
	if activated:
		doc.run_notifications("on_flow_alert")


def _handle_expiry_warning(business_id: str, value: dict) -> None:
	doc = _flow_for(business_id, value)
	if not doc:
		return

	doc.log("Warning", f"Flow {doc.flow_name}: {value.get('warning')}", response_data=value)
	doc.run_notifications("on_flow_alert")


def _flow_for(business_id: str, value: dict):
	if not _account_for(business_id, value):
		return None
	flow_id = value.get("flow_id")
	if not frappe.db.exists("WA Flow", flow_id):
		log(
			"Warning",
			"Flow",
			f"Flow webhook event {value.get('event')} for unknown Flow {flow_id}",
			response_data=value,
		)
		return None
	return frappe.get_doc("WA Flow", flow_id)


def _account_for(business_id: str, value: dict) -> str | None:
	account = frappe.db.get_value("WA Account", {"business_id": business_id}, "name")
	if not account:
		log(
			"Warning",
			"Flow",
			f"Flow webhook event {value.get('event')} for Flow {value.get('flow_id')} "
			f"of unknown business account {business_id}",
			response_data=value,
		)
	return account


def _normalise_error(error: dict) -> dict:
	# Meta's samples spell error types INVALID_SCREEN_TRANSITION, its reference invalid-screen-transition.
	error_type = error.get("error_type", "")
	return {**error, "error_type": error_type.lower().replace("-", "_")}
