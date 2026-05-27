# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

import json

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from whatsapp.whatsapp.api.utils import (
	build_template_message_payload,
	build_text_message_payload,
	log,
)
from whatsapp.whatsapp.api.whatsapp import Whatsapp


class WhatsappMessage(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		context_message_id: DF.Data | None
		conversation_id: DF.Data | None
		direction: DF.Literal["Outgoing", "Incoming"]
		error_code: DF.Data | None
		error_message: DF.LongText | None
		is_template: DF.Check
		media_id: DF.Data | None
		media_url: DF.Data | None
		message: DF.LongText | None
		message_id: DF.Data | None
		mime_type: DF.Data | None
		reference_docname: DF.DynamicLink | None
		reference_doctype: DF.Link | None
		status: DF.Literal["Pending", "Sent", "Delivered", "Read", "Failed"]
		template_body_parameters: DF.Code | None
		template_header_parameters: DF.Code | None
		timestamp: DF.Datetime | None
		to: DF.Link
		whatsapp_account: DF.Link
		whatsapp_template: DF.Link | None
	# end: auto-generated types

	def before_insert(self) -> None:
		if self.direction == "Outgoing" and not self.whatsapp_account:
			default_account = frappe.db.get_single_value("Whatsapp Setting", "default_account")
			if default_account:
				self.whatsapp_account = default_account

	def validate(self) -> None:
		if self.direction == "Outgoing":
			self._validate_outgoing()
			self._set_from_number()
			if self.is_template and self.reference_docname:
				self._populate_template_parameters()

	def before_submit(self) -> None:
		if self.direction == "Outgoing":
			self._send()

	def on_submit(self) -> None:
		if self.direction == "Outgoing" and self.status == "Sent":
			process_append_actions(self, trigger_on="Outgoing")
			self.run_notifications("on_send")

	def _validate_outgoing(self) -> None:
		if not self.to:
			frappe.throw(_("Recipient is required"))
		if not self.whatsapp_account:
			frappe.throw(_("WhatsApp Account is required"))
		self._check_profile_blocked()
		if self.is_template and self.whatsapp_template:
			self._validate_template_reference()

	def _check_profile_blocked(self) -> None:
		profile = frappe.get_cached_doc("Whatsapp Profile", self.to)
		if profile.status == "Blocked":
			frappe.throw(
				_("Cannot send message to blocked profile: {0}").format(profile.profile_name)
			)

	def _set_from_number(self) -> None:
		if not self.get("from") and self.whatsapp_account:
			account = frappe.get_cached_doc("Whatsapp Account", self.whatsapp_account)
			self.set("from", account.phone_id)

	def _validate_template_reference(self) -> None:
		template = frappe.get_cached_doc("Whatsapp Template", self.whatsapp_template)
		if template.template_variables:
			if not self.reference_docname:
				frappe.throw(_("Reference Document is required when template has variables"))

	def _populate_template_parameters(self) -> None:
		template = frappe.get_cached_doc("Whatsapp Template", self.whatsapp_template)
		if not template.reference_doctype:
			return

		ref_doc = frappe.get_doc(template.reference_doctype, self.reference_docname)

		body_params = {}
		header_params = {}

		for var in template.template_variables:
			if not var.variable_field:
				continue
			value = ref_doc.get(var.variable_field)
			check_str = f"{{{{{var.variable_name}}}}}"
			is_header = (
				template.header_type == "TEXT"
				and template.header_text
				and check_str in template.header_text
			)
			if is_header:
				header_params[var.variable_name] = str(value or "")
			else:
				body_params[var.variable_name] = str(value or "")

		self.template_body_parameters = json.dumps(body_params)
		if header_params:
			self.template_header_parameters = json.dumps(next(iter(header_params.values())))

	def _send(self) -> None:
		account = frappe.get_doc("Whatsapp Account", self.whatsapp_account)
		settings = frappe.get_single("Whatsapp Setting")
		client = _get_whatsapp_client(account, settings)

		payload = self._build_payload()
		try:
			log(
				"Info", "Message",
				f"Sending {self.direction} message to {self.to}",
				account=self.whatsapp_account,
				reference_doctype="Whatsapp Message",
				reference_docname=self.name,
				request_data=payload,
			)
			result = client.send_message(payload)
			messages = result.get("messages", [])
			self.message_id = messages[0].get("id") if messages else None
			self.timestamp = now_datetime()
			self.status = "Sent"
			log(
				"Info", "Message",
				f"Message sent successfully to {self.to}, id={self.message_id}",
				account=self.whatsapp_account,
				reference_doctype="Whatsapp Message",
				reference_docname=self.name,
				response_data=result,
			)
		except requests.HTTPError as e:
			self.status = "Failed"
			self.error_message = str(e)
			log(
				"Error", "Message",
				f"Message send failed to {self.to}: {e}",
				account=self.whatsapp_account,
				reference_doctype="Whatsapp Message",
				reference_docname=self.name,
				request_data=payload,
				response_data=getattr(e, "response", None) and e.response.text,
				traceback=frappe.get_traceback(),
			)
			frappe.logger("whatsapp").error("Message send failed", exc_info=True)
			self.db_set("status", "Failed")
			self.db_set("error_message", str(e))
			self.run_notifications("on_send_failed")
			frappe.throw(_("Failed to send message: {0}").format(str(e)))

	def _build_payload(self) -> dict:
		profile = frappe.get_cached_doc("Whatsapp Profile", self.to)
		to_phone = profile.phone_number

		if self.is_template:
			template_doc = frappe.get_doc("Whatsapp Template", self.whatsapp_template)
			body_params = json.loads(self.template_body_parameters or "{}")
			return build_template_message_payload(
				to=to_phone,
				template_doc=template_doc,
				body_parameters=body_params,
				header_parameters=self.template_header_parameters,
			)
		return build_text_message_payload(to=to_phone, text=self.message or "")


def process_append_actions(
	doc, trigger_on: str, sender_phone: str | None = None, sender_name: str | None = None
) -> None:
	"""Create linked documents from the message based on the account's append actions."""
	account = frappe.get_cached_doc("Whatsapp Account", doc.whatsapp_account)
	actions = account.get("append_actions", [])
	if not actions:
		return

	for action in actions:
		if action.trigger_on not in (trigger_on, "Both"):
			continue
		if not action.append_to:
			continue

		try:
			new_doc = frappe.new_doc(action.append_to)

			if action.message_field and doc.message:
				new_doc.set(action.message_field, doc.message)

			sender = sender_phone or doc.get("from")
			if action.sender_field and sender:
				new_doc.set(action.sender_field, sender)

			if action.sender_name_field and sender_name:
				new_doc.set(action.sender_name_field, sender_name)

			if action.timestamp_field and doc.timestamp:
				new_doc.set(action.timestamp_field, doc.timestamp)

			new_doc.insert(ignore_permissions=True)

			doc.reference_doctype = action.append_to
			doc.reference_docname = new_doc.name
		except Exception:
			log(
				"Error", "Message",
				f"Append action failed: could not create {action.append_to} from message",
				account=doc.whatsapp_account,
				reference_doctype="Whatsapp Message",
				reference_docname=doc.name,
				traceback=frappe.get_traceback(),
			)
			frappe.log_error(
				title="WhatsApp Append Action Failed",
				message=f"Failed to create {action.append_to} from message {doc.name}: {frappe.get_traceback()}",
			)

	if doc.reference_doctype:
		doc.db_set("reference_doctype", doc.reference_doctype)
		doc.db_set("reference_docname", doc.reference_docname)


def _get_whatsapp_client(account, settings) -> Whatsapp:
	return Whatsapp(
		args=frappe._dict(
			business_id=account.get("business_id"),
			app_id=account.get("app_id") or "",
			access_token=account.get("access_token"),
			phone_number_id=account.get("phone_id"),
			base_url=settings.get("whatsapp_api_url"),
			api_version=settings.get("whatsapp_api_version"),
			account_name=account.get("name"),
		)
	)
