# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json

import frappe

from whatsapp.whatsapp.flows.outline import FlowOutline, flatten
from whatsapp.whatsapp.flows.send import template_flow_buttons

SUMMARY_SEPARATOR = " · "


class FlowAnswers:
	"""A Flow response's answers, labelled from the Flow's outline, with sensitive values masked."""

	def __init__(self, response: dict, outline: FlowOutline | None):
		self.values = dict(flatten(response))
		self.labels = {answer["key"]: answer["label"] for answer in outline.answers} if outline else {}
		self.sensitive = set(outline.sensitive) if outline else set()

	def rows(self) -> list[dict]:
		"""Answers in the outline's order, then the keys the outline does not know. A masked value is None."""
		known = [key for key in self.labels if key in self.values]
		unknown = [key for key in self.values if key not in self.labels]
		return [self._row(key) for key in known + unknown]

	def summary(self) -> str:
		return SUMMARY_SEPARATOR.join(
			f"{row['label']}: {_display(row['value'])}"
			for row in self.rows()
			if not row["masked"] and row["value"] not in (None, "", [])
		)

	def _row(self, key: str) -> dict:
		masked = key in self.sensitive
		return {
			"key": key,
			"label": self.labels.get(key) or key,
			"value": None if masked else self.values[key],
			"masked": masked,
		}


def template_outline(flow_template: str | None) -> FlowOutline | None:
	"""For a response whose button is unknown: masks every key that any Flow button of the template marks sensitive."""
	if not flow_template:
		return None
	template = frappe.get_cached_doc("WA Template", flow_template)
	flows = {button.flow for _, button in template_flow_buttons(template) if button.flow}
	sensitive = {key for flow in flows for key in frappe.get_doc("WA Flow", flow).get_outline().sensitive}
	return FlowOutline(screens=[], entry_screens={}, answers=[], sensitive=sorted(sensitive))


def _display(value) -> str:
	if isinstance(value, list):
		return ", ".join(_display(item) for item in value)
	if isinstance(value, dict):
		return json.dumps(value)
	return str(value)
