# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe

from whatsapp.whatsapp.api.utils import log

LOCAL_CONFIGURATION = ("flow_inputs", "flow_response_actions")


def prepare_flow_buttons(rows: list[dict], account_name: str, previous_buttons: list) -> None:
	"""Link the synced Flow button rows to their WA Flows and keep the local configuration
	of the buttons they replace, which Meta never holds."""
	flow_rows = [row for row in rows if row["button_type"] == "Flow"]
	for row in flow_rows:
		_link_flow(row, account_name)
	_carry_over(flow_rows, [button for button in previous_buttons if button.button_type == "Flow"])


def _link_flow(row: dict, account_name: str) -> None:
	flow_id = row["flow"]
	if not flow_id or frappe.db.exists("WA Flow", flow_id):
		return
	from whatsapp.whatsapp.flows.sync import sync_flow  # it imports wa_template, which imports this module

	try:
		sync_flow(account_name, flow_id)
	except Exception:
		row["flow"] = ""
		log(
			"Error",
			"Template",
			f"Could not sync Flow {flow_id} for the template button '{row['button_text']}'; the button keeps no Flow",
			account=account_name,
		)


def _carry_over(rows: list[dict], previous: list) -> None:
	"""Match each row to a previous button by Flow, then by position among the Flow buttons."""
	unmatched = list(previous)
	matches = {}
	for index, row in enumerate(rows):
		same_flow = next((button for button in unmatched if row["flow"] and button.flow == row["flow"]), None)
		if same_flow:
			matches[index] = same_flow
			unmatched.remove(same_flow)
	for index in range(min(len(rows), len(previous))):
		if index not in matches and previous[index] in unmatched:
			matches[index] = previous[index]
			unmatched.remove(previous[index])
	for index, button in matches.items():
		rows[index].update({field: button.get(field) for field in LOCAL_CONFIGURATION})
