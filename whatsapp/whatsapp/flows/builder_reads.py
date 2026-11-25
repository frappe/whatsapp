# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.query_builder.functions import Count

from whatsapp.whatsapp.flows.authoring import split_categories, templates_using
from whatsapp.whatsapp.flows.template_validation import MESSAGE_SOURCES


@frappe.whitelist()
def get_flow_list(account: str | None = None) -> list[dict]:
	"""The Flows list, newest change first; with `account`, only the Flows of its business.

	Row: {name, flow_name, status, categories: [str], modified, used_by: number of templates}
	"""
	filters = {}
	if account:
		filters["business_id"] = frappe.db.get_value("WA Account", account, "business_id")
	rows = frappe.get_list(
		"WA Flow",
		filters=filters,
		fields=["name", "flow_name", "status", "categories", "modified"],
		order_by="modified desc",
	)
	used_by = _template_counts([row.name for row in rows])
	for row in rows:
		row.categories = split_categories(row.categories)
		row.used_by = used_by.get(row.name, 0)
	return rows


@frappe.whitelist()
def get_flow_for_builder(name: str) -> dict:
	"""Everything the builder opens a Flow with.

	`modified` is the token `save_flow` expects back. `used_keys` maps each answer key that a
	Response action maps to the templates mapping it; `used_inputs` does the same for the entry
	screen data keys that Flow inputs fill. A template is `{name, template_label}`.
	"""
	flow = frappe.get_doc("WA Flow", name)
	flow.check_permission("read")
	used_keys, used_inputs = _key_usage(name)
	return {
		"name": flow.name,
		"flow_name": flow.flow_name,
		"flow_json": flow.flow_json,
		"status": flow.status,
		"business_id": flow.business_id,
		"modified": str(flow.modified),
		"validation_errors": frappe.parse_json(flow.validation_errors) or [],
		"used_keys": used_keys,
		"used_inputs": used_inputs,
	}


def _template_counts(flows: list[str]) -> dict[str, int]:
	if not flows:
		return {}
	button = frappe.qb.DocType("WA Template Button")
	return dict(
		frappe.qb.from_(button)
		.select(button.flow, Count(button.parent).distinct())
		.where(
			(button.parenttype == "WA Template") & (button.button_type == "Flow") & button.flow.isin(flows)
		)
		.groupby(button.flow)
		.run()
	)


def _key_usage(flow: str) -> tuple[dict, dict]:
	used_keys, used_inputs = {}, {}
	for template in templates_using(flow):
		ref = {"name": template.name, "template_label": template.template_label}
		for button in template.buttons:
			for key in _mapped_answer_keys(button):
				_add(used_keys, key, ref)
			for row in frappe.parse_json(button.flow_inputs) or []:
				_add(used_inputs, row.get("key"), ref)
	return used_keys, used_inputs


def _mapped_answer_keys(button) -> list[str]:
	"""A dotted source (`address.city`) uses the answer key before the first dot."""
	sources = [
		mapping.get("source") or ""
		for action in frappe.parse_json(button.flow_response_actions) or []
		for mapping in action.get("fields") or []
	]
	return [source.split(".")[0] for source in sources if source and source not in MESSAGE_SOURCES]


def _add(usage: dict, key: str | None, ref: dict) -> None:
	if key and ref not in usage.setdefault(key, []):
		usage[key].append(ref)
