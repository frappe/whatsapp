# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

import json

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from whatsapp.whatsapp.api.utils import (
	build_interactive_buttons_payload,
	build_interactive_list_payload,
	build_media_message_payload,
	build_reaction_message_payload,
	build_template_message_payload,
	build_text_message_payload,
	log,
)
from whatsapp.whatsapp.api.whatsapp import WhatsApp


class WhatsAppMessage(Document):
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
			default_account = frappe.db.get_single_value("WhatsApp Settings", "default_account")
			if default_account:
				self.whatsapp_account = default_account

	def after_insert(self) -> None:
		self.notify_change()

	def validate(self) -> None:
		if self.direction == "Outgoing":
			self._validate_outgoing()
			self._set_from_number()
			self._resolve_reply_to_context()
			self._validate_interactive()
			if self.is_template and self.reference_docname:
				self._populate_template_parameters()

	def before_submit(self) -> None:
		if self.direction == "Outgoing":
			self._send()

	def on_submit(self) -> None:
		if self.direction == "Outgoing" and self.status == "Sent":
			process_append_actions(self, trigger_on="Outgoing")
			self.run_notifications("on_send")

	def on_trash(self) -> None:
		frappe.db.delete(
			"WhatsApp Log",
			{"reference_doctype": "WhatsApp Message", "reference_docname": self.name},
		)
		self.notify_change()

	def notify_change(self) -> None:
		"""Tell any host rendering the reference document to refetch its messages.

		`after_commit` keeps a client from refetching rows the transaction has not written
		yet. Paths that write with `frappe.db.set_value` skip controller hooks and must call
		this themselves.
		"""
		frappe.publish_realtime(
			"whatsapp_message",
			{
				"reference_doctype": self.reference_doctype,
				"reference_docname": self.reference_docname,
			},
			after_commit=True,
		)

	def _validate_outgoing(self) -> None:
		if not self.to:
			frappe.throw(_("Recipient is required"))
		if not self.whatsapp_account:
			frappe.throw(_("WhatsApp Account is required"))
		self._check_profile_blocked()
		if self.is_template and self.whatsapp_template:
			self._validate_template_reference()

	def _check_profile_blocked(self) -> None:
		profile = frappe.get_cached_doc("WhatsApp Profile", self.to)
		if profile.status == "Blocked":
			frappe.throw(
				_("Cannot send message to blocked profile: {0}").format(profile.profile_name)
			)

	def _set_from_number(self) -> None:
		if not self.get("from") and self.whatsapp_account:
			account = frappe.get_cached_doc("WhatsApp Account", self.whatsapp_account)
			self.set("from", account.phone_id)

	def _validate_interactive(self) -> None:
		buttons = self.get("interactive_buttons") or []
		list_items = self.get("interactive_list_items") or []
		if buttons and list_items:
			frappe.throw(_("Cannot have both interactive buttons and list items"))
		if len(buttons) > 3:
			frappe.throw(_("Maximum 3 interactive buttons allowed"))
		if len(list_items) > 10:
			frappe.throw(_("Maximum 10 list items allowed"))

	def _resolve_reply_to_context(self) -> None:
		if self.reply_to_message:
			replied = frappe.get_doc("WhatsApp Message", self.reply_to_message)
			self.context_message_id = replied.message_id

	def _validate_template_reference(self) -> None:
		template = frappe.get_cached_doc("WhatsApp Template", self.whatsapp_template)
		if template.template_variables:
			if not self.reference_docname:
				frappe.throw(_("Reference Document is required when template has variables"))

	def _populate_template_parameters(self) -> None:
		template = frappe.get_cached_doc("WhatsApp Template", self.whatsapp_template)
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

	def _get_mime_type(self, file_name: str) -> str:
		ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
		mime_map = {
			"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
			"gif": "image/gif", "webp": "image/webp",
			"mp4": "video/mp4", "3gp": "video/3gp",
			"mp3": "audio/mpeg", "ogg": "audio/ogg",
			"pdf": "application/pdf", "doc": "application/msword",
			"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
		}
		return mime_map.get(ext, "application/octet-stream")

	def _send(self) -> None:
		account = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
		settings = frappe.get_single("WhatsApp Settings")
		client = _get_whatsapp_client(account, settings)

		if self.attach and not self.is_template:
			file_doc = frappe.get_doc("File", self.attach)
			file_content = file_doc.get_content()
			file_name = file_doc.file_name
			mime_type = getattr(file_doc, "content_type", None) or self._get_mime_type(file_name)
			try:
				media_result = client.upload_media(file_content, mime_type, file_name)
				self.media_id = media_result.get("id")
				self.mime_type = mime_type
			except requests.HTTPError as e:
				self.status = "Failed"
				self.error_message = str(e)
				log(
					"Error", "Message",
					f"Media upload failed for {self.to}: {e}",
					account=self.whatsapp_account,
					reference_doctype="WhatsApp Message",
					reference_docname=self.name,
					traceback=frappe.get_traceback(),
				)
				self.db_set("status", "Failed")
				self.db_set("error_message", str(e))
				self.run_notifications("on_send_failed")
				frappe.throw(_("Failed to upload media: {0}").format(str(e)))

		if self.is_template and self.whatsapp_template:
			template_doc = frappe.get_doc("WhatsApp Template", self.whatsapp_template)
			if template_doc.header_type in ("IMAGE", "DOCUMENT", "VIDEO", "GIF") and template_doc.header_media:
				if not template_doc.header_media_handle:
					file_doc = frappe.get_doc("File", template_doc.header_media)
					file_content = file_doc.get_content()
					file_name = file_doc.file_name
					mime_type = getattr(file_doc, "content_type", None) or self._get_mime_type(file_name)
					try:
						media_result = client.upload_media(file_content, mime_type, file_name)
						handle = media_result.get("id")
						frappe.db.set_value("WhatsApp Template", template_doc.name, "header_media_handle", handle)
						template_doc.header_media_handle = handle
						template_doc.mime_type = mime_type
						frappe.db.set_value("WhatsApp Template", template_doc.name, "mime_type", mime_type)
					except requests.HTTPError as e:
						self.status = "Failed"
						self.error_message = str(e)
						log(
							"Error", "Message",
							f"Template header media upload failed for {self.to}: {e}",
							account=self.whatsapp_account,
							reference_doctype="WhatsApp Message",
							reference_docname=self.name,
							traceback=frappe.get_traceback(),
						)
						self.db_set("status", "Failed")
						self.db_set("error_message", str(e))
						self.run_notifications("on_send_failed")
						frappe.throw(_("Failed to upload template header media: {0}").format(str(e)))

		payload = self._build_payload()
		try:
			log(
				"Info", "Message",
				f"Sending {self.direction} message to {self.to}",
				account=self.whatsapp_account,
				reference_doctype="WhatsApp Message",
				reference_docname=self.name,
				request_data=payload,
			)
			result = client.send_message(payload)
			messages = result.get("messages", [])
			self.message_id = self.message_id or (messages[0].get("id") if messages else None)
			self.timestamp = now_datetime()
			self.status = "Sent"
			log(
				"Info", "Message",
				f"Message sent successfully to {self.to}, id={self.message_id}",
				account=self.whatsapp_account,
				reference_doctype="WhatsApp Message",
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
				reference_doctype="WhatsApp Message",
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
		profile = frappe.get_cached_doc("WhatsApp Profile", self.to)
		to_phone = profile.phone_number

		buttons = self.get("interactive_buttons") or []
		list_items = self.get("interactive_list_items") or []

		if self.reaction is not None and self.context_message_id and not self.is_template:
			return build_reaction_message_payload(
				to=to_phone,
				message_id=self.context_message_id,
				emoji=self.reaction or None,
			)

		if buttons and not self.is_template:
			return build_interactive_buttons_payload(
				to=to_phone,
				body_text=self.message or "",
				buttons=[{"title": b.title, "id": b.button_id} for b in buttons],
			)
		if list_items and not self.is_template:
			return build_interactive_list_payload(
				to=to_phone,
				body_text=self.message or "",
				items=[{"title": i.title, "description": i.description, "id": i.list_item_id} for i in list_items],
			)

		if self.attach and not self.is_template and self.media_id:
			return build_media_message_payload(
				to=to_phone,
				media_id=self.media_id,
				mime_type=self.mime_type,
				caption=self.message or None,
				file_name=frappe.db.get_value("File", self.attach, "file_name"),
			)

		if self.is_template:
			template_doc = frappe.get_cached_doc("WhatsApp Template", self.whatsapp_template)
			body_params = json.loads(self.template_body_parameters or "{}")

			header_params = self.template_header_parameters
			if template_doc.header_type in ("IMAGE", "DOCUMENT", "VIDEO", "GIF") and template_doc.header_media_handle:
				if not header_params:
					header_params = json.dumps({"id": template_doc.header_media_handle})

			payload = build_template_message_payload(
				to=to_phone,
				template_doc=template_doc,
				body_parameters=body_params,
				header_parameters=header_params,
			)
		else:
			payload = build_text_message_payload(to=to_phone, text=self.message or "")

		if self.context_message_id:
			payload["context"] = {"message_id": self.context_message_id}

		return payload


def process_append_actions(
	doc, trigger_on: str, sender_phone: str | None = None, sender_name: str | None = None
) -> None:
	"""Create linked documents from the message based on the account's append actions."""
	account = frappe.get_cached_doc("WhatsApp Account", doc.whatsapp_account)
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
				reference_doctype="WhatsApp Message",
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


def _get_whatsapp_client(account, settings) -> WhatsApp:
	return WhatsApp(
		args=frappe._dict(
			business_id=account.get("business_id"),
			app_id=account.get("app_id") or "",
			access_token=account.get_password("access_token"),
			phone_number_id=account.get("phone_id"),
			base_url=settings.get("whatsapp_api_url"),
			api_version=settings.get("whatsapp_api_version"),
			account_name=account.get("name"),
		)
	)
