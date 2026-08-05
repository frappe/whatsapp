# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

"""Conversation API: read a document's WhatsApp messages, and send/react from it.

The read's scope is handed in as `[doctype, docname]` references and each one is
permission-checked, so a host decides what a "conversation" is without this app knowing
anything about that host. The wire model uses the DocType's own field names, unrenamed.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from whatsapp.whatsapp.api.utils import (
	humanize_error_message,
	log,
	mime_type_for_content_type,
	parse_template_parameters,
)
from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import get_or_create_profile

MESSAGE_FIELDS = [
	"name",
	"direction",
	"to",
	"from",
	"mime_type",
	"is_template",
	"media_url",
	"whatsapp_template",
	"message_id",
	"context_message_id",
	"creation",
	"message",
	"status",
	"reference_doctype",
	"reference_docname",
	"template_body_parameters",
	"template_header_parameters",
	"reaction",
	"error_message",
]


@frappe.whitelist()
def get_messages(references: str) -> list[dict]:
	"""Return the WhatsApp Messages attached to the given reference documents.

	`references` is a client-supplied JSON list of `[doctype, docname]` pairs, so every
	pair is checked for existence and read permission first.
	"""
	pairs = _validate_references(references)
	if not pairs:
		return []

	messages = []
	for reference_doctype, reference_docname in pairs:
		messages += frappe.get_all(
			"WhatsApp Message",
			filters={
				"reference_doctype": reference_doctype,
				"reference_docname": reference_docname,
			},
			fields=MESSAGE_FIELDS,
			order_by="creation asc, name asc",
		)

	for message in messages:
		message["error_message"] = humanize_error_message(message.get("error_message"))

	messages = _fold_reactions(messages)
	_render_templates(messages)
	_resolve_replies(messages)
	_attach_file_details(messages)

	return messages


@frappe.whitelist()
def send_message(
	to: str,
	message: str = "",
	attach: str | None = None,
	content_type: str = "text",
	reply_to: str | None = None,
	reference_doctype: str | None = None,
	reference_docname: str | None = None,
) -> str:
	"""Send a text or media message and return the created WhatsApp Message's name."""
	if not (message or "").strip() and not attach:
		frappe.throw(_("Cannot send an empty message."))

	if reference_doctype and reference_docname:
		_validate_reference(reference_doctype, reference_docname)

	# Before anything is created: an attachment resolving to no File would otherwise leave
	# a message with no body and no media.
	file_docname = _resolve_attachment(attach) if attach else None

	profile_name = _resolve_to_profile(to, create_if_missing=True)
	if not profile_name:
		frappe.throw(
			_(
				"Could not resolve recipient '{0}' to a WhatsApp Profile. "
				"Please ensure a default WhatsApp account is configured."
			).format(to)
		)

	doc = frappe.new_doc("WhatsApp Message")
	doc.update(
		{
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
			# The caption for media; never fall back to the file URL, which would be
			# sent verbatim as a text message.
			"message": message or "",
			"to": profile_name,
		}
	)

	if reply_to:
		doc.context_message_id = _resolve_reply_context(reply_to)

	if attach:
		doc.attach = file_docname

	doc.insert(ignore_permissions=True)

	if attach:
		# media_url is read-only, and this mime_type is only a pre-send display value —
		# _send overwrites it with the File's real content type.
		frappe.db.set_value("WhatsApp Message", doc.name, "media_url", attach, update_modified=False)
		frappe.db.set_value(
			"WhatsApp Message",
			doc.name,
			"mime_type",
			mime_type_for_content_type(content_type),
			update_modified=False,
		)
		doc.reload()

	_submit(doc, f"Failed to send message to {profile_name}")
	return doc.name


@frappe.whitelist()
def react_to_message(message: str, emoji: str) -> str:
	"""React to a message with `emoji` and return the created reaction message's name.

	A reaction is its own message document; `get_messages` folds it back onto its target.
	"""
	target = _get_permitted_message(message)
	context_message_id = _acknowledged_message_id(target, _("react to"))

	doc = frappe.new_doc("WhatsApp Message")
	doc.update(
		{
			"reference_doctype": target.reference_doctype,
			"reference_docname": target.reference_docname,
			"message": emoji,
			"reaction": emoji,
			"to": target.to,
			"context_message_id": context_message_id,
		}
	)
	doc.insert(ignore_permissions=True)

	_submit(doc, f"Failed to send reaction to message {target.name}")
	return doc.name


@frappe.whitelist()
def send_template(
	template: str,
	to: str,
	reference_doctype: str | None = None,
	reference_docname: str | None = None,
) -> str:
	"""Send an approved template and return the created WhatsApp Message's name."""
	if reference_doctype and reference_docname:
		_validate_reference(reference_doctype, reference_docname)

	_validate_template_for_reference(template, reference_doctype)
	_validate_template_is_approved(template)

	profile_name = _resolve_to_profile(to, create_if_missing=True)
	if not profile_name:
		frappe.throw(
			_(
				"Could not resolve recipient '{0}' to a WhatsApp Profile. "
				"Please ensure a default WhatsApp account is configured."
			).format(to)
		)

	doc = frappe.new_doc("WhatsApp Message")
	doc.update(
		{
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
			"is_template": True,
			"message": "Template message",
			"whatsapp_template": template,
			"to": profile_name,
		}
	)
	doc.insert(ignore_permissions=True)

	_submit(doc, f"Failed to send template {template} to {profile_name}")
	return doc.name


def _validate_references(references: str) -> list[tuple[str, str]]:
	"""Parse the client-supplied reference list, dropping duplicates.

	The security boundary of `get_messages`: the caller chooses the scope, so every pair
	is checked for existence and read permission.
	"""
	try:
		parsed = frappe.parse_json(references or "[]") or []
	except ValueError:
		frappe.throw(_("references must be a JSON list of [doctype, docname] pairs."))

	if not isinstance(parsed, list):
		frappe.throw(_("references must be a JSON list of [doctype, docname] pairs."))

	pairs = []
	for reference in parsed:
		if not isinstance(reference, list | tuple) or len(reference) != 2 or not all(reference):
			frappe.throw(_("Each reference must be a [doctype, docname] pair."))
		_validate_reference(reference[0], reference[1])
		pairs.append((reference[0], reference[1]))

	return list(dict.fromkeys(pairs))


def _validate_reference(reference_doctype: str, reference_docname: str) -> None:
	"""Throw unless the reference document exists and the session user may read it."""
	if not frappe.db.exists("DocType", reference_doctype):
		frappe.throw(_("DocType {0} does not exist.").format(reference_doctype), frappe.DoesNotExistError)

	if not frappe.db.exists(reference_doctype, reference_docname):
		frappe.throw(
			_("Reference document {0} {1} does not exist.").format(reference_doctype, reference_docname),
			frappe.DoesNotExistError,
		)

	if not frappe.get_doc(reference_doctype, reference_docname).has_permission("read"):
		frappe.throw(
			_("Not permitted to access reference document {0} {1}.").format(
				reference_doctype, reference_docname
			),
			frappe.PermissionError,
		)


def _conversation_order(message: dict) -> tuple:
	"""Oldest first, null-safe.

	The leading flag groups nulls: substituting "" for a missing `creation` would compare
	`str` to `datetime` and raise. `name` breaks same-second ties across references.
	"""
	creation = message.get("creation")
	return (creation is not None, creation or "", message.get("name") or "")


def _fold_reactions(messages: list[dict]) -> list[dict]:
	"""Fold reaction rows onto the message they target and drop the rows themselves.

	Each participant keeps one reaction per message, so the latest per (target, direction)
	wins. A row is a reaction when `reaction` is non-null, not when it is truthy: a
	retraction arrives as the same row with an *empty* emoji and removes what it retracts,
	while a non-reaction message stores NULL.
	"""
	reactions_by_target: dict[str, dict[str, str]] = {}
	folded = []

	for message in sorted(messages, key=_conversation_order):
		if message.get("reaction") is None or not message.get("context_message_id"):
			folded.append(message)
			continue

		target = reactions_by_target.setdefault(message["context_message_id"], {})
		if message["reaction"]:
			target[message["direction"]] = message["reaction"]
		else:
			target.pop(message["direction"], None)

	for message in folded:
		target = reactions_by_target.get(message.get("message_id"), {})
		message["reactions"] = [
			{"emoji": emoji, "direction": direction} for direction, emoji in target.items()
		]

	return folded


def _render_templates(messages: list[dict]) -> None:
	"""Resolve each template message's header, body, footer and buttons for display."""
	for message in messages:
		template_name = message.get("whatsapp_template")
		if not message.get("is_template") or not template_name:
			continue
		if not frappe.db.exists("WhatsApp Template", template_name):
			continue

		template = frappe.get_cached_doc("WhatsApp Template", template_name)
		message["template_name"] = template.template_name
		message["template"] = parse_template_parameters(
			template.message, _parsed_parameters(message.get("template_body_parameters"))
		)
		message["header"] = parse_template_parameters(
			template.header_text, _parsed_parameters(message.get("template_header_parameters"))
		)
		message["footer"] = template.footer
		message["buttons"] = [
			{
				"button_type": button.button_type,
				"button_text": button.button_text,
				"url": button.url,
				"phone_number": button.phone_number,
			}
			for button in (template.buttons or [])
		]


def _parsed_parameters(stored: str | None):
	"""Decode a stored template parameter blob, tolerating empty or malformed values."""
	if not stored:
		return None
	try:
		return frappe.parse_json(stored)
	except ValueError:
		return None


def _resolve_replies(messages: list[dict]) -> None:
	"""Quote the replied-to message on each reply.

	Only reply-specific keys are set: a template message that is itself a reply keeps
	its own rendered `header` and `footer`.
	"""
	by_message_id = {m["message_id"]: m for m in messages if m.get("message_id")}

	for message in messages:
		replied = by_message_id.get(message.get("context_message_id"))
		if not replied:
			continue
		message["reply_message"] = (
			replied.get("template") if replied.get("is_template") else replied.get("message")
		)
		message["reply_to"] = replied["name"]
		message["reply_to_direction"] = replied["direction"]


def _attach_file_details(messages: list[dict]) -> None:
	"""Add the source File's name and size to media messages, in one batched query."""
	media_urls = list({m["media_url"] for m in messages if m.get("media_url")})
	if not media_urls:
		return

	files = frappe.get_all(
		"File",
		filters={"file_url": ["in", media_urls]},
		fields=["file_url", "file_name", "file_size"],
	)
	file_map = {f.file_url: f for f in files}

	for message in messages:
		file_info = file_map.get(message.get("media_url"))
		if file_info:
			message["file_name"] = file_info.file_name
			message["file_size"] = file_info.file_size


def _get_permitted_message(name: str) -> Document:
	"""Load a WhatsApp Message the session user may read, along with its reference doc."""
	if not frappe.db.exists("WhatsApp Message", name):
		frappe.throw(_("Referenced WhatsApp message does not exist."), frappe.DoesNotExistError)

	doc = frappe.get_doc("WhatsApp Message", name)
	if not doc.has_permission("read"):
		frappe.throw(_("Not permitted to access the referenced WhatsApp message."), frappe.PermissionError)

	if doc.reference_doctype and doc.reference_docname:
		_validate_reference(doc.reference_doctype, doc.reference_docname)

	return doc


def _acknowledged_message_id(target: Document, action: str) -> str:
	"""Return the target's WhatsApp `message_id`, throwing if Meta has not issued one yet.

	Thrown here because the send path degrades silently: with no `context_message_id` a
	reaction goes out as a text message of the bare emoji, and a reply loses its quote.
	"""
	if not target.message_id:
		frappe.throw(
			_("Cannot {0} message {1}: WhatsApp has not acknowledged it yet (status {2}).").format(
				action, target.name, target.status or _("Pending")
			)
		)

	return target.message_id


def _resolve_reply_context(reply_to: str) -> str:
	"""Return the WhatsApp message_id a reply should quote."""
	return _acknowledged_message_id(_get_permitted_message(reply_to), _("reply to"))


def _resolve_attachment(file_url: str) -> str:
	"""Resolve a client-supplied file URL to the File docname the send path expects.

	`WhatsAppMessage._send` resolves `attach` as a File docname, so a URL must be mapped.
	Copies share a `file_url`, so the oldest — the original upload — wins.
	"""
	file_docname = frappe.db.get_value(
		"File", {"file_url": file_url}, "name", order_by="creation asc, name asc"
	)
	if not file_docname:
		frappe.throw(
			_("No File found for attachment '{0}'.").format(file_url),
			frappe.DoesNotExistError,
		)

	return file_docname


def _get_default_whatsapp_account() -> str | None:
	return frappe.db.get_single_value("WhatsApp Settings", "default_account")


def _resolve_to_profile(to_value: str, create_if_missing: bool = False) -> str | None:
	"""Resolve a WhatsApp Profile name or a phone number to a WhatsApp Profile name.

	A phone number is looked up against the default account, and optionally created.
	Returns None when it cannot be resolved.
	"""
	if not to_value:
		return None

	if frappe.db.exists("WhatsApp Profile", to_value):
		return to_value

	default_account = _get_default_whatsapp_account()
	if not default_account:
		return None

	profile_name = frappe.db.get_value(
		"WhatsApp Profile",
		{"phone_number": to_value, "whatsapp_account": default_account},
		"name",
	)
	if profile_name:
		return profile_name

	if not create_if_missing:
		return None

	try:
		return get_or_create_profile(
			phone_number=to_value,
			account_name=default_account,
			profile_name=to_value,
			wa_id=to_value,
		)
	except Exception as e:
		log(
			"Error",
			"Message",
			f"Failed to resolve or create a WhatsApp Profile for {to_value}: {e}",
			account=default_account,
			traceback=frappe.get_traceback(),
		)
		return None


def _validate_template_is_approved(template_name: str) -> None:
	"""Throw unless the template is Approved.

	Meta will not render an unapproved template, so reject it here rather than let it
	become a Failed message — the endpoint takes any name, not just what a picker offered.
	"""
	status = frappe.db.get_value("WhatsApp Template", template_name, "status")
	if status != "Approved":
		frappe.throw(
			_("WhatsApp Template '{0}' is {1} and cannot be sent; only Approved templates can.").format(
				template_name, status or _("not approved")
			)
		)


def _validate_template_for_reference(template_name: str, reference_doctype: str | None) -> None:
	"""Enforce the "reference DocType drives all parameters" invariant.

	Variables resolve from one document of the template's bound reference_doctype, so
	sending from a different doctype (or none) cannot fill them. See DESIGN_DECISIONS.md.
	"""
	if not frappe.db.exists("WhatsApp Template", template_name):
		frappe.throw(
			_("WhatsApp Template '{0}' does not exist.").format(template_name),
			frappe.DoesNotExistError,
		)

	template = frappe.get_cached_doc("WhatsApp Template", template_name)
	if not template.get("template_variables"):
		return

	template_ref = template.get("reference_doctype")
	if not template_ref:
		frappe.throw(
			_(
				"Template '{0}' has unfilled variables but is not bound to a reference DocType, "
				"so variable values cannot be auto-filled."
			).format(template_name)
		)

	if template_ref != reference_doctype:
		frappe.throw(
			_("Template '{0}' resolves variables from {1}; cannot send from {2}.").format(
				template_name, template_ref, reference_doctype or _("no reference document")
			)
		)

	unmapped = [var.variable_name for var in template.get("template_variables") if not var.variable_field]
	if unmapped:
		frappe.throw(
			_(
				"Template '{0}' has variables without a mapped field: {1}. "
				"Set Variable Field on each Template Variable row before sending."
			).format(template_name, ", ".join(unmapped))
		)


def _submit(doc: Document, failure_summary: str) -> None:
	"""Submit an already-inserted message, recording any failure on the record itself.

	Re-raising would roll back the request, discarding the row and the log entry that
	explains it. The message_log is drained because `_send` throws: its message would
	otherwise reach the client as an error dialog on an HTTP 200, beside the Failed bubble.
	"""
	message_log_depth = len(frappe.get_message_log())
	try:
		doc.submit()
	except Exception as e:
		while len(frappe.get_message_log()) > message_log_depth:
			frappe.clear_last_message()

		log(
			"Error",
			"Message",
			f"{failure_summary}: {e}",
			account=doc.whatsapp_account,
			reference_doctype="WhatsApp Message",
			reference_docname=doc.name,
			traceback=frappe.get_traceback(),
		)
		if frappe.db.get_value("WhatsApp Message", doc.name, "status") != "Failed":
			frappe.db.set_value(
				"WhatsApp Message",
				doc.name,
				{"status": "Failed", "error_message": str(e)},
				update_modified=False,
			)
