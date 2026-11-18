# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from collections.abc import Callable
from typing import TYPE_CHECKING

import frappe
import requests
from frappe import _

from whatsapp.whatsapp.api.utils import log
from whatsapp.whatsapp.doctype.wa_template.wa_template import _get_whatsapp_client
from whatsapp.whatsapp.flows.sync import known_status, sync_flow

if TYPE_CHECKING:
	from whatsapp.whatsapp.doctype.wa_flow.wa_flow import WAFlow

DEPRECATABLE_STATUSES = ("Published", "Throttled", "Blocked")


@frappe.whitelist()
def publish_flow(name: str) -> dict:
	"""Return the Flow's state after Meta's publish, in the shape of `flow_state`."""
	flow = flow_to_write(name)
	if flow.status != "Draft":
		frappe.throw(_("Only a Draft Flow can be published. This one is {0}.").format(_(flow.status)))
	if flow.validation_errors:
		frappe.throw(_("Fix the Flow's validation errors before you publish it."))
	_run_on_meta(flow, "publish_flow", _("Could not publish the Flow"))
	_log_action(flow, "Published")
	return flow_state(flow.reload())


@frappe.whitelist()
def deprecate_flow(name: str) -> None:
	flow = flow_to_write(name)
	if flow.status not in DEPRECATABLE_STATUSES:
		frappe.throw(
			_("Only a Published, Throttled or Blocked Flow can be deprecated. This one is {0}.").format(
				_(flow.status)
			)
		)
	_run_on_meta(flow, "deprecate_flow", _("Could not deprecate the Flow"))
	_log_action(flow, "Deprecated")


@frappe.whitelist()
def refresh_flow(name: str) -> None:
	flow = flow_to_write(name)
	on_meta(flow, _("Could not refresh the Flow"), lambda: sync_flow(flow.whatsapp_account, flow.flow_id))


def upload_flow_json(flow: "WAFlow") -> None:
	"""Meta saves JSON with validation errors as a draft, so they are stored and do not block the save."""
	client = _get_whatsapp_client(flow.whatsapp_account)
	upload = on_meta(
		flow,
		_("Could not upload the Flow JSON"),
		lambda: client.update_flow_json(flow.flow_id, flow.flow_json),
	)
	errors = upload.get("validation_errors") or []
	flow.validation_errors = frappe.as_json(errors) if errors else None
	# Editing a Published Flow can move it back to Draft on Meta.
	details = on_meta(flow, _("Could not refresh the Flow"), lambda: client.get_flow(flow.flow_id))
	flow.status = known_status(details.get("status"), flow)
	log(
		"Info",
		"Flow",
		f"Uploaded the Flow JSON of {flow.flow_name}: {len(errors)} validation errors, status={flow.status}",
		account=flow.whatsapp_account,
		reference_doctype="WA Flow",
		reference_docname=flow.name,
		response_data=upload,
	)


def flow_state(flow: "WAFlow") -> dict:
	"""What the builder shows after a change: `modified` is the token for the next save."""
	return {
		"status": flow.status,
		"modified": str(flow.modified),
		"validation_errors": frappe.parse_json(flow.validation_errors) or [],
	}


def flow_to_write(name: str) -> "WAFlow":
	flow = frappe.get_doc("WA Flow", name)
	flow.check_permission("write")
	return flow


def _run_on_meta(flow: "WAFlow", method: str, failure: str) -> None:
	client = _get_whatsapp_client(flow.whatsapp_account)
	on_meta(flow, failure, lambda: getattr(client, method)(flow.flow_id))
	sync_flow(flow.whatsapp_account, flow.flow_id)


def on_meta(flow: "WAFlow", failure: str, call: Callable):
	try:
		return call()
	except requests.RequestException as e:
		log(
			"Error",
			"Flow",
			f"{failure} {flow.flow_name} ({flow.flow_id}): {e}",
			account=flow.whatsapp_account,
			reference_doctype="WA Flow",
			reference_docname=flow.name,
		)
		frappe.throw(f"{failure}: {e}")


def _log_action(flow: "WAFlow", action: str) -> None:
	log(
		"Info",
		"Flow",
		f"{action} Flow {flow.flow_name} on Meta",
		account=flow.whatsapp_account,
		reference_doctype="WA Flow",
		reference_docname=flow.name,
	)
