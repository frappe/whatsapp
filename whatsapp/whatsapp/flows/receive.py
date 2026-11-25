# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
from functools import cached_property

import frappe
from frappe import _

from whatsapp.whatsapp.api.utils import log
from whatsapp.whatsapp.flows.answers import FlowAnswers, response_outline
from whatsapp.whatsapp.flows.outline import FlowOutline
from whatsapp.whatsapp.flows.send import template_flow_buttons
from whatsapp.whatsapp.flows.token import FlowToken

SEND_FIELDS = ["name", "flow", "is_template", "whatsapp_template", "reference_doctype", "reference_docname"]


def flow_response_fields(msg: dict, profile: str, account: str) -> dict:
	"""The WA Message fields of an incoming completed Flow (`nfm_reply`); nothing for any other message."""
	interactive = msg.get("interactive") or {}
	if msg.get("type") != "interactive" or interactive.get("type") != "nfm_reply":
		return {}
	return FlowResponse(msg, profile, account).fields()


class FlowResponse:
	"""An `nfm_reply`, matched to the message that sent its Flow."""

	def __init__(self, msg: dict, profile: str, account: str):
		self.msg = msg
		self.profile = profile
		self.account = account
		self.reply = msg["interactive"].get("nfm_reply") or {}
		self.answers = self._parse_answers()
		token = self.answers.pop("flow_token", None)
		self.token = FlowToken.parse(str(token)) if token else None

	def fields(self) -> dict:
		fields = {"flow_response": json.dumps(self.answers)}
		if self.send:
			fields.update(self._inherited())
		outline = self._outline(fields)
		sensitive = outline.sensitive if outline else []
		fields["flow_sensitive_keys"] = json.dumps(sensitive)
		fields["message"] = self._summary(outline, sensitive) if self.send else _("Form submitted")
		return fields

	@cached_property
	def send(self) -> frappe._dict | None:
		return self._send_by_token() or self._send_by_context()

	def _send_by_token(self) -> frappe._dict | None:
		if not self.token:
			return None
		return self._find_send({"flow_token": self.token.base})

	def _send_by_context(self) -> frappe._dict | None:
		context_id = (self.msg.get("context") or {}).get("id")
		if not context_id:
			return None
		return self._find_send({"message_id": context_id, "flow_token": ("is", "set")})

	def _find_send(self, filters: dict) -> frappe._dict | None:
		return frappe.db.get_value(
			"WA Message",
			{"direction": "Outgoing", "to": self.profile, **filters},
			SEND_FIELDS,
			as_dict=True,
		)

	def _inherited(self) -> dict:
		fields = {
			"reply_to_message": self.send.name,
			"reference_doctype": self.send.reference_doctype,
			"reference_docname": self.send.reference_docname,
		}
		if not self.send.is_template:
			return {**fields, "flow": self.send.flow}
		return {**fields, **self._template_button()}

	def _template_button(self) -> dict:
		template = self.send.whatsapp_template
		buttons = dict(template_flow_buttons(frappe.get_cached_doc("WA Template", template)))
		if self.token and self.token.flow:
			return self._named_button(template, buttons)
		return self._lone_button(template, buttons)

	def _named_button(self, template: str, buttons: dict) -> dict:
		"""Match the token's button only while the template still has its Flow at that index;
		otherwise keep the sent Flow for masking, without the template, so no Response actions run."""
		index, flow = self.token.button_index, self.token.flow
		button = buttons.get(index)
		if button and button.flow == flow:
			return {"flow_template": template, "flow_button_index": index, "flow": flow}
		self._warn(
			f"Flow response {self.msg.get('id')} answers button {index} of template {template}, "
			f"which no longer opens Flow {flow}. It is stored without its button, and runs no Response actions."
		)
		if frappe.db.exists("WA Flow", flow):
			return {"flow": flow}
		return {"flow_template": template}

	def _lone_button(self, template: str, buttons: dict) -> dict:
		# Meta drops the flow_token on some iOS clients, so only a lone Flow button is certain.
		if len(buttons) == 1:
			index, button = next(iter(buttons.items()))
			return {"flow_template": template, "flow_button_index": index, "flow": button.flow}
		self._warn(
			f"Flow response {self.msg.get('id')} has no button index, and template {template} "
			"has several Flow buttons. It is stored without its Flow, and runs no Response actions."
		)
		return {"flow_template": template}

	def _parse_answers(self) -> dict:
		try:
			answers = json.loads(self.reply.get("response_json") or "{}")
		except ValueError:
			answers = None
		if isinstance(answers, dict):
			return answers
		self._warn(f"Flow response {self.msg.get('id')} is not valid JSON. Its answers are stored as {{}}.")
		return {}

	def _outline(self, fields: dict) -> FlowOutline | None:
		flow = fields.get("flow")
		return response_outline(flow and frappe.get_doc("WA Flow", flow), fields.get("flow_template"))

	def _summary(self, outline: FlowOutline | None, sensitive: list[str]) -> str:
		return FlowAnswers(self.answers, outline, sensitive).summary() or self.reply.get("body") or ""

	def _warn(self, message: str) -> None:
		log("Warning", "Flow", message, account=self.account, request_data=self.msg)
