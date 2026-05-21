# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

import datetime
import hashlib
import hmac
import json

import frappe
from frappe import _

MESSAGE_FIELDS = frozenset({"messages", "message_template_status_update"})


@frappe.whitelist(allow_guest=True, methods=["GET"])
def handler() -> str:
	"""Verify webhook with Meta challenge-response."""
	mode = frappe.form_dict.get("hub.mode")
	token = frappe.form_dict.get("hub.verify_token")
	challenge = frappe.form_dict.get("hub.challenge")

	if mode != "subscribe" or not token or not challenge:
		frappe.response.http_status_code = 403
		return "invalid request"

	settings = frappe.get_single("Whatsapp Setting")
	if token != (settings.get("webhook_verify_token") or ""):
		frappe.response.http_status_code = 403
		return "token mismatch"

	frappe.response["content_type"] = "text/plain"
	return challenge


@frappe.whitelist(allow_guest=True, methods=["POST"])
def handler() -> dict:
	"""Receive incoming webhook events from Meta."""
	payload = frappe.local.form_dict

	settings = frappe.get_single("Whatsapp Setting")
	secret = settings.get("webhook_secret")
	if secret:
		_verify_signature(secret)

	for entry in payload.get("entry", []):
		for change in entry.get("changes", []):
			field = change.get("field")
			value = change.get("value", {})

			if field == "messages":
				_handle_messages(value)
			elif field == "message_template_status_update":
				_handle_template_status(value)

	return {"status": "ok"}


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

	account_name = frappe.db.get_value("Whatsapp Account", {"phone_id": phone_number_id}, "name")
	if not account_name:
		frappe.log_error(
			title="WhatsApp Webhook",
			message=f"No account found for phone_number_id={phone_number_id}",
		)
		return

	for msg in value.get("messages", []):
		_create_incoming_message(msg, account_name)

	for status in value.get("statuses", []):
		_update_message_status(status)


def _create_incoming_message(msg: dict, account_name: str) -> None:
	msg_type = msg.get("type", "text")

	if msg_type == "text":
		content = msg.get("text", {}).get("body", "")
	elif msg_type == "button":
		content = msg.get("button", {}).get("text", "")
	elif msg_type == "interactive":
		content = msg.get("interactive", {}).get("button_reply", {}).get("title", "")
	else:
		content = ""

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
			"doctype": "Whatsapp Message",
			"to": msg.get("from"),
			"from": msg.get("to"),
			"message": content,
			"whatsapp_account": account_name,
			"direction": "Incoming",
			"status": "Sent",
			"message_id": msg.get("id"),
			"timestamp": timestamp_val,
			"context_message_id": msg.get("context", {}).get("id") if msg.get("context") else None,
			**media_fields,
		}
	)
	doc.insert(ignore_permissions=True)


def _update_message_status(status: dict) -> None:
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

	frappe.db.set_value("Whatsapp Message", {"message_id": message_id}, updates)


def _handle_template_status(value: dict) -> None:
	template_id = value.get("message_template_id")
	if not template_id:
		return

	api_status = value.get("status", "")
	status_map = {
		"APPROVED": "APPROVED",
		"REJECTED": "REJECTED",
		"PENDING": "PENDING",
		"PENDING_DELETION": "PENDING",
	}
	local_status = status_map.get(api_status, "PENDING")
	frappe.db.set_value(
		"Whatsapp Template", {"whatsapp_template_id": template_id}, "status", local_status
	)
