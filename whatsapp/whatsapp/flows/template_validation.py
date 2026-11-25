# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe import _

from whatsapp.whatsapp.mapping import (
	INPUT_FIELD_TYPES,
	SOURCE_FIELD_TYPES,
	validate_list_doctype,
	validate_mapped_field,
)

MESSAGE_SOURCES = (
	"sender_phone",
	"sender_name",
	"reference_doctype",
	"reference_name",
	"received_at",
	"whole_response",
)
RESPONSE_ACTIONS = ("Update Reference", "Create Document")
MAX_LABEL_LENGTH = 25


def validate_flow_buttons(template) -> None:
	"""Check each Flow button of a template, and default its screen to the Flow's first entry screen."""
	types = {button.button_type for button in template.buttons}
	# The push leaves Copy Code out, so Meta would index the Flow buttons differently from the send.
	if {"Flow", "Copy Code"} <= types:
		frappe.throw(_("A template with a Flow button cannot have a Copy Code button."))
	for button in template.buttons:
		if button.button_type == "Flow":
			FlowButtonValidation(template, button).validate()


class FlowButtonValidation:
	def __init__(self, template, button):
		self.template = template
		self.button = button
		self.where = _("Button #{0} ({1})").format(button.idx, button.button_text)
		self.outline = None

	def validate(self) -> None:
		self._validate_flow()
		self._validate_label()
		self.outline = frappe.get_doc("WA Flow", self.button.flow).get_outline()
		if self.outline.screens:
			self._validate_screen()
		else:
			self._warn(
				_(
					"{0}: Flow {1} has no outline, because its Flow JSON is missing or invalid. Its screen, inputs and answers are not checked."
				).format(self.where, self.button.flow)
			)
		for index, row in enumerate(self._rows("flow_inputs"), 1):
			self._validate_input(_("{0}, Flow input #{1}").format(self.where, index), row)
		for index, action in enumerate(self._rows("flow_response_actions"), 1):
			self._validate_action(_("{0}, Response action #{1}").format(self.where, index), action)

	def _validate_flow(self) -> None:
		if not self.button.flow:
			frappe.throw(_("{0}: choose the Flow this button opens").format(self.where))
		flow = frappe.db.get_value("WA Flow", self.button.flow, ["status", "business_id"], as_dict=True)
		if flow is None:
			frappe.throw(_("{0}: Flow {1} does not exist").format(self.where, self.button.flow))
		if self.template.whatsapp_account and flow.business_id != self._template_business_id():
			frappe.throw(
				_("{0}: Flow {1} belongs to another WhatsApp Business Account than the template").format(
					self.where, self.button.flow
				)
			)
		if flow.status == "Deprecated":
			frappe.throw(
				_("{0}: Flow {1} is Deprecated, and Meta does not send deprecated Flows").format(
					self.where, self.button.flow
				)
			)

	def _template_business_id(self) -> str | None:
		return frappe.db.get_value("WA Account", self.template.whatsapp_account, "business_id")

	def _validate_label(self) -> None:
		if len(self.button.button_text or "") > MAX_LABEL_LENGTH:
			frappe.throw(
				_("{0}: a Flow button label can have at most {1} characters").format(
					self.where, MAX_LABEL_LENGTH
				)
			)

	def _validate_screen(self) -> None:
		entry_screens = self.outline.entry_screens
		if not self.button.flow_screen:
			self.button.flow_screen = next(iter(entry_screens), "")
		elif self.button.flow_screen not in entry_screens:
			frappe.throw(
				_("{0}: {1} is not an entry screen of the Flow. Choose one of: {2}").format(
					self.where, self.button.flow_screen, ", ".join(entry_screens)
				)
			)

	def _validate_input(self, where: str, row: dict) -> None:
		reference_meta = self._reference_meta(where, _("fill Flow inputs"))
		key = _required(row, "key", where)
		declared = self.outline.entry_screens.get(self.button.flow_screen, {})
		if self.outline.screens and key not in declared:
			frappe.throw(
				_("{0}: the entry screen {1} does not declare {2}").format(
					where, self.button.flow_screen, key
				)
			)
		declared_type = declared.get(key, "unknown")
		if declared_type not in INPUT_FIELD_TYPES:
			frappe.throw(
				_("{0}: {1} is declared as {2}; only string, number and boolean inputs can be filled").format(
					where, key, declared_type
				)
			)
		validate_mapped_field(
			reference_meta,
			_required(row, "source_field", where),
			INPUT_FIELD_TYPES[declared_type],
			where,
			_("Source field"),
		)

	def _validate_action(self, where: str, action: dict) -> None:
		kind = action.get("action")
		if kind not in RESPONSE_ACTIONS:
			frappe.throw(
				_("{0}: {1} is not a Response action. Use one of: {2}").format(
					where, kind, ", ".join(RESPONSE_ACTIONS)
				)
			)
		if kind == "Update Reference":
			target_meta = self._reference_meta(where, _("update the reference document"))
			_require_permission(where, target_meta.name, "write")
		else:
			target_meta = _create_target(where, action.get("doctype"))
			_require_permission(where, target_meta.name, "create")
		_validate_condition(where, action.get("condition"))
		writable_levels = target_meta.get_permlevel_access("write")
		for index, mapping in enumerate(action.get("fields") or [], 1):
			self._validate_mapping(
				_("{0}, field #{1}").format(where, index), mapping, target_meta, writable_levels
			)

	def _validate_mapping(self, where: str, mapping: dict, target_meta, writable_levels: set[int]) -> None:
		source_type = self._source_type(where, _required(mapping, "source", where))
		target_field = _required(mapping, "target_field", where)
		validate_mapped_field(
			target_meta, target_field, SOURCE_FIELD_TYPES[source_type], where, _("Target field")
		)
		permlevel = target_meta.get_field(target_field).permlevel
		if permlevel and permlevel not in writable_levels:
			frappe.throw(
				_("{0}: you cannot write the Target field '{1}' on {2}").format(
					where, target_field, target_meta.name
				)
			)

	def _source_type(self, where: str, source: str) -> str:
		if source in MESSAGE_SOURCES:
			return source
		answer = next((answer for answer in self.outline.answers if answer["key"] == source), None)
		if answer:
			return answer["type"]
		if self.outline.screens:
			self._warn(
				_(
					"{0}: the current version of the Flow does not send {1}. Responses from older versions may still carry it."
				).format(where, source)
			)
		return "unknown"

	def _reference_meta(self, where: str, purpose: str):
		if not self.template.reference_doctype:
			frappe.throw(_("{0}: set the template's Reference DocType to {1}").format(where, purpose))
		return frappe.get_meta(self.template.reference_doctype)

	def _rows(self, fieldname: str) -> list[dict]:
		rows = frappe.parse_json(self.button.get(fieldname)) or []
		if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
			frappe.throw(
				_("{0}: {1} must be a list of objects").format(
					self.where, _(self.button.meta.get_label(fieldname))
				)
			)
		return rows

	def _warn(self, message: str) -> None:
		frappe.msgprint(message, title=_("Check the Flow button"), indicator="orange")


def _create_target(where: str, doctype: str | None):
	if not doctype or not frappe.db.exists("DocType", doctype):
		frappe.throw(
			_("{0}: Create Document needs an existing DocType, not '{1}'").format(where, doctype or "")
		)
	target_meta = frappe.get_meta(doctype)
	validate_list_doctype(target_meta, where)
	return target_meta


def _require_permission(where: str, doctype: str, ptype: str) -> None:
	"""Response actions run without permission checks, so the author must hold what they configure."""
	if not frappe.has_permission(doctype, ptype):
		frappe.throw(
			_("{0}: you need {1} permission on {2} to configure this action").format(where, ptype, doctype)
		)


def _validate_condition(where: str, condition: str | None) -> None:
	if not condition:
		return
	try:
		compile(condition, "<condition>", "eval")
	except SyntaxError as e:
		frappe.throw(_("{0}: the condition is not a Python expression: {1}").format(where, e.msg))


def _required(row: dict, key: str, where: str) -> str:
	if not row.get(key):
		frappe.throw(_("{0}: {1} is missing").format(where, key))
	return row[key]
