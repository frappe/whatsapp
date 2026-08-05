# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import datetime
import hashlib
import hmac
import json

import frappe
from frappe import _
from frappe.core.doctype.server_script.server_script_utils import (
	run_server_script_for_doc_event,
)
from werkzeug.wrappers import Response

from whatsapp.whatsapp.api.utils import log, normalize_template_status
from whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message import (
	_get_whatsapp_client,
	process_append_actions,
)
from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import (
	get_or_create_profile,
)

MESSAGE_FIELDS = frozenset({"messages", "message_template_status_update"})


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def handler():
	"""Dispatch Meta webhook requests: GET verifies, POST delivers events."""
	if frappe.request.method == "GET":
		return _verify()
	return _receive()


def _verify() -> Response:
	"""Verify webhook with Meta challenge-response.

	Meta requires the raw hub.challenge string as the response body. Returning
	a werkzeug Response bypasses Frappe's default as_json() builder, which
	would otherwise emit {"message": "<challenge>"} with Content-Type
	application/json and fail Meta's exact-match check.
	"""
	mode = frappe.form_dict.get("hub.mode")
	token = frappe.form_dict.get("hub.verify_token")
	challenge = frappe.form_dict.get("hub.challenge")

	if mode != "subscribe" or not token or not challenge:
		return Response("invalid request", status=403, mimetype="text/plain")

	settings = frappe.get_single("WhatsApp Settings")
	if token != (settings.get("webhook_verify_token") or ""):
		return Response("token mismatch", status=403, mimetype="text/plain")

	log("Info", "Webhook", "Webhook verified successfully")
	return Response(challenge, status=200, mimetype="text/plain")


def _receive() -> str:
	"""Receive incoming webhook events from Meta. Always 200 + Content-Type: text/plain."""
	payload = frappe.local.form_dict

	settings = frappe.get_single("WhatsApp Settings")
	secret = settings.get("webhook_secret")
	if secret:
		try:
			_verify_signature(secret)
		except Exception:
			log("Error", "Webhook", "HMAC signature verification failed", request_data=payload)
			raise

	log("Info", "Webhook", "Webhook payload received", request_data=payload)

	for entry in payload.get("entry", []):
		for change in entry.get("changes", []):
			field = change.get("field")
			value = change.get("value", {})

			if field == "messages":
				_handle_messages(value)
			elif field == "message_template_status_update":
				_handle_template_status(value)

	frappe.response.http_status_code = 200
	frappe.response["content_type"] = "text/plain"
	return "ok"


def _verify_signature(secret: str) -> None:
	raw = frappe.local.request.get_data(as_text=True)
	expected = frappe.get_request_header("X-Hub-Signature-256", "")
	if not expected.startswith("sha256="):
		frappe.throw(_("Invalid signature header"), frappe.AuthenticationError)

	digest = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
	if not hmac.compare_digest(f"sha256={digest}", expected):
		frappe.throw(_("HMAC signature mismatch"), frappe.AuthenticationError)


def _handle_messages(value: dict) -> None:
	metadata = value.get("metadata", {})
	phone_number_id = metadata.get("phone_number_id")

	account_name = frappe.db.get_value("WhatsApp Account", {"phone_id": phone_number_id}, "name")
	if not account_name:
		default_account = frappe.db.get_single_value("WhatsApp Settings", "default_account")
		if default_account:
			account_name = default_account
		else:
			msg = f"No account found for phone_number_id={phone_number_id} and no default account set"
			log("Error", "Webhook", msg, response_data=value)
			frappe.log_error(title="WhatsApp Webhook", message=msg)
			return

	contacts = value.get("contacts", [])
	contact_profile = contacts[0].get("profile", {}) if contacts else {}

	for msg in value.get("messages", []):
		_create_incoming_message(msg, account_name, contact_profile)

	for status in value.get("statuses", []):
		_update_message_status(status, account_name)


def _create_incoming_message(msg: dict, account_name: str, contact_profile: dict | None = None) -> None:
	message_id = msg.get("id")
	if message_id and frappe.db.exists("WhatsApp Message", {"message_id": message_id}):
		log(
			"Info",
			"Webhook",
			f"Duplicate webhook delivery for message_id={message_id} ignored",
			account=account_name,
			request_data=msg,
		)
		return

	wa_id = msg.get("from", "")
	profile_name = (contact_profile or {}).get("name", "")

	profile = get_or_create_profile(
		phone_number=wa_id,
		account_name=account_name,
		profile_name=profile_name or None,
		wa_id=wa_id,
	)

	msg_type = msg.get("type", "text")

	if msg_type == "reaction":
		reaction_data = msg.get("reaction", {})
		content = reaction_data.get("emoji", "")
		context_id = reaction_data.get("message_id")
		reaction_emoji_val = content
	else:
		if msg_type == "text":
			content = msg.get("text", {}).get("body", "")
		elif msg_type == "button":
			content = msg.get("button", {}).get("text", "")
		elif msg_type == "interactive":
			interactive = msg.get("interactive", {})
			button_reply = interactive.get("button_reply", {})
			list_reply = interactive.get("list_reply", {})
			content = button_reply.get("title", "") or list_reply.get("title", "")
		else:
			content = ""
		context_id = msg.get("context", {}).get("id") if msg.get("context") else None
		reaction_emoji_val = None

	media_fields = {}
	if msg_type in ("image", "audio", "document", "video", "sticker"):
		media = msg.get(msg_type, {})
		media_fields = {
			"media_id": media.get("id"),
			"mime_type": media.get("mime_type"),
		}
		if msg_type == "document":
			media_fields["media_url"] = media.get("filename", "")

	timestamp_val = None
	raw_ts = msg.get("timestamp")
	if raw_ts:
		timestamp_val = datetime.datetime.fromtimestamp(int(raw_ts))

	doc = frappe.get_doc(
		{
			"doctype": "WhatsApp Message",
			"to": profile,
			"from": msg.get("to"),
			"message": content,
			"whatsapp_account": account_name,
			"direction": "Incoming",
			"status": "Sent",
			"message_id": message_id,
			"timestamp": timestamp_val,
			"reaction": reaction_emoji_val,
			"context_message_id": context_id,
			**media_fields,
		}
	)
	# Submit incoming messages (don't leave them as drafts) so docstatus is consistent
	# with outgoing messages. before_submit/_send only act on Outgoing, so submitting an
	# incoming message never triggers an API send.
	doc.flags.ignore_permissions = True
	doc.submit()
	process_append_actions(doc, trigger_on="Incoming", sender_phone=wa_id, sender_name=profile_name)
	doc.run_notifications("on_receive")

	account_doc = frappe.get_cached_doc("WhatsApp Account", account_name)
	if account_doc.get("auto_read_receipts") and doc.get("message_id"):
		settings = frappe.get_single("WhatsApp Settings")
		try:
			client = _get_whatsapp_client(account_doc, settings)
			client.mark_as_read(doc.message_id)
		except Exception:
			log(
				"Warning",
				"Webhook",
				f"Failed to send read receipt for {doc.message_id}",
				account=account_name,
				reference_doctype="WhatsApp Message",
				reference_docname=doc.name,
				traceback=frappe.get_traceback(),
			)

	log(
		"Info",
		"Webhook",
		f"Incoming {msg_type} message from {wa_id} ({profile_name})",
		account=account_name,
		reference_doctype="WhatsApp Message",
		reference_docname=doc.name,
		request_data=msg,
	)


def _update_message_status(status: dict, account_name: str | None = None) -> None:
	message_id = status.get("id")
	if not message_id:
		return

	status_map = {
		"sent": "Sent",
		"delivered": "Delivered",
		"read": "Read",
		"failed": "Failed",
	}
	new_status = status_map.get(status.get("status"), "Pending")

	updates = {"status": new_status}

	conversation = status.get("conversation", {})
	if conversation.get("id"):
		updates["conversation_id"] = conversation["id"]

	errors = status.get("errors", [])
	if errors:
		updates["error_message"] = json.dumps(errors)

	name = frappe.db.get_value("WhatsApp Message", {"message_id": message_id}, "name")
	if not name:
		log(
			"Warning",
			"Webhook",
			f"Status update for unknown message_id={message_id} status={new_status}",
			account=account_name,
			response_data=status,
		)
		return

	old_status = frappe.db.get_value("WhatsApp Message", name, "status")
	if old_status == new_status:
		return

	frappe.db.set_value("WhatsApp Message", name, updates)
	doc = frappe.get_doc("WhatsApp Message", name)
	doc.notify_change()
	doc.run_notifications("on_status_update")
	run_server_script_for_doc_event(doc, "on_update")

	log_level = "Warning" if new_status == "Failed" else "Info"
	log(
		log_level,
		"Webhook",
		f"Message {message_id} status changed: {old_status} -> {new_status}",
		account=account_name,
		reference_doctype="WhatsApp Message",
		reference_docname=name,
		response_data=status,
	)


def _handle_template_status(value: dict) -> None:
	template_id = value.get("message_template_id")
	if not template_id:
		return

	local_status = normalize_template_status(value.get("status", ""))

	name = frappe.db.get_value("WhatsApp Template", {"whatsapp_template_id": template_id}, "name")
	if not name:
		log(
			"Warning",
			"Webhook",
			f"Status update for unknown template_id={template_id} status={local_status}",
			response_data=value,
		)
		return

	old_status = frappe.db.get_value("WhatsApp Template", name, "status")
	if old_status == local_status:
		return

	frappe.db.set_value("WhatsApp Template", name, "status", local_status)
	doc = frappe.get_doc("WhatsApp Template", name)
	if local_status == "Approved":
		doc.run_notifications("on_template_approved")
	elif local_status == "Rejected":
		doc.run_notifications("on_template_rejected")
	run_server_script_for_doc_event(doc, "on_update")

	log(
		"Info",
		"Webhook",
		f"Template {doc.template_name} status changed: {old_status} -> {local_status}",
		reference_doctype="WhatsApp Template",
		reference_docname=name,
		response_data=value,
	)
