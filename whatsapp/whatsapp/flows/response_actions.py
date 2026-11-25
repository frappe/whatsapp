# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import copy
import json
from functools import cached_property

import frappe
from frappe.utils import get_datetime

from whatsapp.whatsapp.api.utils import log
from whatsapp.whatsapp.flows.answers import response_outline
from whatsapp.whatsapp.flows.field_values import UnconvertibleValue, to_field_value
from whatsapp.whatsapp.flows.send import template_flow_buttons

MISSING = object()


def run_response_actions(message) -> None:
	"""Run the Response actions of the Flow button a response answers, each in its own savepoint."""
	sources = ResponseSources(message)
	for action in _configured_actions(message):
		ResponseAction(message, action, sources).run()


class ResponseAction:
	def __init__(self, message, action: dict, sources: "ResponseSources"):
		self.message = message
		self.action = action
		self.sources = sources
		self.kind = action.get("action")

	def run(self) -> None:
		savepoint = f"flow_action_{frappe.generate_hash(length=8)}"
		frappe.db.savepoint(savepoint)
		try:
			self._run()
		except Exception:
			frappe.db.rollback(save_point=savepoint)
			self._log("Error", f"Response action {self.kind} failed", traceback=frappe.get_traceback())

	def _run(self) -> None:
		reference = self.sources.reference()
		if not self._condition_holds(reference):
			return
		if self.kind == "Update Reference":
			self._update(reference)
		else:
			self._create()

	def _update(self, reference) -> None:
		if reference is None:
			self._log(
				"Warning", "Response action Update Reference skipped: the message has no reference document"
			)
			return
		self._set_fields(reference)
		reference.save(ignore_permissions=True)
		self._log("Info", f"Response action Update Reference updated {reference.doctype} {reference.name}")

	def _create(self) -> None:
		document = frappe.new_doc(self.action["doctype"])
		self._set_fields(document)
		document.insert(ignore_permissions=True)
		self._log("Info", f"Response action Create Document created {document.doctype} {document.name}")

	def _condition_holds(self, reference) -> bool:
		condition = self.action.get("condition")
		if not condition:
			return True
		names = {
			"response": _attribute_dict(self.sources.answers),
			"doc": reference.as_dict() if reference else None,
			"message": self.message.as_dict(),
		}
		return bool(frappe.safe_eval(condition, None, names))

	def _set_fields(self, document) -> None:
		for mapping in self.action.get("fields") or []:
			value = self.sources.value(mapping["source"])
			if value is MISSING:
				continue
			df = document.meta.get_field(mapping["target_field"])
			try:
				document.set(df.fieldname, to_field_value(df, value))
			except UnconvertibleValue as e:
				self._log("Warning", f"Response action {self.kind}: {e}")

	def _log(self, level: str, message: str, traceback: str | None = None) -> None:
		log(
			level,
			"Flow",
			message,
			account=self.message.whatsapp_account,
			reference_doctype="WA Message",
			reference_docname=self.message.name,
			traceback=traceback,
		)


class ResponseSources:
	"""The values a Response action can map: answers by key or dotted path, and the message's details."""

	def __init__(self, message):
		self.message = message
		self.answers = frappe.parse_json(message.flow_response) or {}

	def value(self, source: str):
		"""MISSING when the source has no value, so that it is never written as empty."""
		getter = self._message_sources.get(source)
		value = getter() if getter else self._answer(source)
		return MISSING if value is None else value

	def reference(self):
		"""Loaded fresh for each action, so a rolled-back action leaves no changes on it."""
		if not (self.message.reference_doctype and self.message.reference_docname):
			return None
		return frappe.get_doc(self.message.reference_doctype, self.message.reference_docname)

	@cached_property
	def _message_sources(self) -> dict:
		return {
			"sender_phone": lambda: self._profile.phone_number,
			"sender_name": lambda: self._profile.profile_name,
			"reference_doctype": lambda: self.message.reference_doctype,
			"reference_name": lambda: self.message.reference_docname,
			"received_at": lambda: get_datetime(self.message.timestamp or self.message.creation),
			"whole_response": lambda: json.dumps(self._without_sensitive()),
		}

	@cached_property
	def _profile(self):
		return frappe.get_cached_doc("WA Profile", self.message.to)

	def _without_sensitive(self) -> dict:
		flow = frappe.get_doc("WA Flow", self.message.flow) if self.message.flow else None
		outline = response_outline(flow, self.message.flow_template)
		answers = copy.deepcopy(self.answers)
		for path in outline.sensitive if outline else []:
			*parents, key = path.split(".")
			parent = answers
			for name in parents:
				parent = parent.get(name) if isinstance(parent, dict) else None
			if isinstance(parent, dict):
				parent.pop(key, None)
		return answers

	def _answer(self, path: str):
		value = self.answers
		for key in path.split("."):
			if not isinstance(value, dict):
				return None
			value = value.get(key)
		return value


def _configured_actions(message) -> list[dict]:
	# flow_button_index is an Int, so an unmatched button reads 0: only a button that still opens the
	# message's Flow is trusted.
	if not (message.flow_template and message.flow):
		return []
	template = frappe.get_cached_doc("WA Template", message.flow_template)
	button = dict(template_flow_buttons(template)).get(message.flow_button_index)
	if not (button and button.flow == message.flow):
		return []
	return frappe.parse_json(button.flow_response_actions) or []


def _attribute_dict(value):
	if isinstance(value, dict):
		return frappe._dict({key: _attribute_dict(item) for key, item in value.items()})
	if isinstance(value, list):
		return [_attribute_dict(item) for item in value]
	return value
