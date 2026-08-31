# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import re
from collections.abc import Iterator
from typing import cast

import frappe
from frappe import _
from frappe.model.document import Document

from whatsapp.whatsapp.api.languages import SUPPORTED_LANGUAGES
from whatsapp.whatsapp.api.utils import (
	build_create_template_payload,
	log,
	normalize_template_status,
	parse_whatsapp_template_to_doc,
	run_access_guards,
)
from whatsapp.whatsapp.api.whatsapp import WhatsApp
from whatsapp.whatsapp.doctype.whatsapp_account.whatsapp_account import WhatsAppAccount
from whatsapp.whatsapp.doctype.whatsapp_settings.whatsapp_settings import WhatsAppSettings


class WhatsAppTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from whatsapp.whatsapp.doctype.template_variable.template_variable import TemplateVariable
		from whatsapp.whatsapp.doctype.whatsapp_template_button.whatsapp_template_button import (
			WhatsAppTemplateButton,
		)

		buttons: DF.Table[WhatsAppTemplateButton]
		footer: DF.Data | None
		header_media: DF.Attach | None
		header_media_handle: DF.Data | None
		header_text: DF.Data | None
		header_type: DF.Literal["Text", "Image", "Document", "GIF", "Video"]
		language: DF.Link
		message: DF.Code
		mime_type: DF.Data | None
		reference_doctype: DF.Link | None
		status: DF.Literal["Pending", "Approved", "Rejected", "Deleted"]
		template_label: DF.Data
		template_name: DF.Data | None
		template_type: DF.Literal["Utility", "Marketing", "Authentication"]
		template_variables: DF.Table[TemplateVariable]
		variable_format: DF.Literal["Named", "Positional"]
		whatsapp_account: DF.Link | None
		whatsapp_template_id: DF.Data | None
	# end: auto-generated types

	def _sync_template_variables(self) -> None:
		if self.header_text and self.header_type == "Text":
			header_variables = get_template_variables(self.header_text)
		else:
			header_variables = []

		body_variables = get_template_variables(self.message)

		all_variables = list(dict.fromkeys([*header_variables, *body_variables]))

		if not all_variables:
			self.set("template_variables", [])
			return

		existing = {v.variable_name: v for v in self.template_variables}
		new_rows = []
		for var_name in all_variables:
			if var_name in existing:
				new_rows.append(existing[var_name])
			else:
				new_rows.append({"variable_name": var_name, "variable_example": "", "variable_field": ""})

		self.set("template_variables", new_rows)

	def validate_template_variables(self) -> None:
		variables = get_template_variables(self.message)
		if self.header_text and self.header_type == "Text":
			variables.extend(get_template_variables(self.header_text))

		if len(variables) != len(self.template_variables):
			frappe.throw(
				"Number of template variables in table does not match the number of variables in the message"
			)

		for variable in self.template_variables:
			if variable.variable_name not in variables:
				frappe.throw(f"Variable {variable.variable_name} not found in message")

	def _set_mime_type(self) -> None:
		if not self.header_media:
			self.mime_type = None
			return

		if self.mime_type and not self.has_value_changed("header_media"):
			return

		try:
			file_doc = frappe.get_doc("File", {"file_url": self.header_media})
			if file_doc.content_type:
				self.mime_type = file_doc.content_type
				return
		except frappe.DoesNotExistError:
			pass

		ext = self.header_media.rsplit(".", 1)[-1].lower() if "." in self.header_media else ""
		mime_map = {
			"jpg": "image/jpeg",
			"jpeg": "image/jpeg",
			"png": "image/png",
			"gif": "image/gif",
			"pdf": "application/pdf",
			"mp4": "video/mp4",
			"webm": "video/webm",
			"mp3": "audio/mpeg",
			"ogg": "audio/ogg",
		}
		self.mime_type = mime_map.get(ext, "")

	def validate_template_name(self) -> None:
		if not self.template_name:
			frappe.throw("Template name is required")
			return

		if len(self.template_name) > 512:
			frappe.throw("Template name should not exceed 512 characters")

		if not re.match(r"^[a-zA-Z0-9_]+$", self.template_name):
			frappe.throw("Template name should only contain alphanumeric characters and underscores")

	def on_validate(self) -> None:
		self.validate_template_variables()
		self.validate_template_name()

	def _derive_template_name(self) -> None:
		"""Locked once pushed to Meta, which doesn't allow a rename, and never overridden
		during Meta-driven sync."""
		if self.flags.get("from_sync") or self.whatsapp_template_id:
			return

		derived = normalize_string(self.template_label)
		if derived == self.template_name:
			return

		frappe.logger("whatsapp", allow_site=True, max_size=10_485_760).info(
			"_derive_template_name | old=%s new=%s", self.template_name, derived
		)
		self.template_name = derived

	def before_save(self) -> None:
		logger = frappe.logger("whatsapp", allow_site=True, max_size=10_485_760)
		logger.info(
			"before_save | template_label=%s template_name=%s whatsapp_template_id=%s __islocal=%s",
			self.template_label,
			self.template_name,
			self.whatsapp_template_id,
			self.get("__islocal"),
		)

		self._derive_template_name()
		self._sync_template_variables()
		self._set_mime_type()

		if self.flags.get("from_sync"):
			logger.info("before_save | from_sync flag set, skipping Meta API calls")
			return

		if not self.whatsapp_template_id:
			logger.info("before_save | no whatsapp_template_id, proceeding to push to Meta")
			self._push_to_meta()
		elif self.get("__islocal"):
			logger.info(
				"before_save | __islocal with whatsapp_template_id=%s, already created by API, skipping",
				self.whatsapp_template_id,
			)
		else:
			logger.info(
				"before_save | template has whatsapp_template_id=%s, updating in Meta",
				self.whatsapp_template_id,
			)
			self._update_in_meta()

	def _push_to_meta(self) -> None:
		logger = frappe.logger("whatsapp", allow_site=True, max_size=10_485_760)
		logger.info(
			"_push_to_meta | start | template_label=%s template_name=%s",
			self.template_label,
			self.template_name,
		)

		if not self.whatsapp_account:
			logger.error("_push_to_meta | whatsapp_account is not set")
			log(
				"Error",
				"Template",
				"Cannot push template: WhatsApp Account not set",
				account=self.whatsapp_account,
			)
			frappe.throw(_("WhatsApp Account is required to push template to Meta"))

		whatsapp = _get_whatsapp_client(self.whatsapp_account)

		if not self.variable_format:
			self.variable_format = "Named"

		payload = build_create_template_payload(self)
		logger.info("_push_to_meta | payload=%s", payload)

		ref_doctype, ref_docname = self._log_reference()

		try:
			logger.info("_push_to_meta | calling Meta API create_template...")
			result = whatsapp.create_template(payload)
			logger.info("_push_to_meta | Meta API response | result=%s", result)
		except Exception as e:
			logger.error("_push_to_meta | Meta API call failed | error=%s", e, exc_info=True)
			log(
				"Error",
				"Template",
				f"Failed to push template {self.template_label} to Meta: {e}",
				account=self.whatsapp_account,
				reference_doctype=ref_doctype,
				reference_docname=ref_docname,
				request_data=payload,
				traceback=frappe.get_traceback(),
			)
			frappe.throw(_("Failed to push template to Meta: {0}").format(str(e)))

		template_id = result.get("id")
		if not template_id:
			logger.error("_push_to_meta | Meta API returned no id | full_response=%s", result)
			log(
				"Error",
				"Template",
				f"Meta API returned no template ID for {self.template_label}",
				account=self.whatsapp_account,
				reference_doctype=ref_doctype,
				reference_docname=ref_docname,
				request_data=payload,
				response_data=result,
			)
			frappe.throw(_("Meta API did not return a template ID"))

		self.whatsapp_template_id = template_id
		self.status = normalize_template_status(result.get("status", ""))
		logger.info("_push_to_meta | success | whatsapp_template_id=%s status=%s", template_id, self.status)
		log(
			"Info",
			"Template",
			f"Template {self.template_label} pushed to Meta, id={template_id}, status={self.status}",
			account=self.whatsapp_account,
			reference_doctype=ref_doctype,
			reference_docname=ref_docname,
			request_data=payload,
			response_data=result,
		)

	def _log_reference(self) -> tuple[str | None, str | None]:
		"""Return (doctype, name) safe to use as a WhatsApp Log DynamicLink.

		Skipped when the doc isn't yet persisted — _push_to_meta runs inside
		before_save, so the row doesn't exist for Frappe's link validator.
		"""
		if self.is_new() or not frappe.db.exists("WhatsApp Template", self.name):
			return None, None
		return "WhatsApp Template", self.name

	def _update_in_meta(self) -> None:
		logger = frappe.logger("whatsapp", allow_site=True, max_size=10_485_760)
		logger.info(
			"_update_in_meta | start | template_label=%s template_name=%s",
			self.template_label,
			self.template_name,
		)

		if not self.whatsapp_account:
			logger.error("_update_in_meta | whatsapp_account is not set")
			log(
				"Error",
				"Template",
				"Cannot update template: WhatsApp Account not set",
				account=self.whatsapp_account,
			)
			frappe.throw(_("WhatsApp Account is required to update template in Meta"))

		whatsapp = _get_whatsapp_client(self.whatsapp_account)

		if not self.variable_format:
			self.variable_format = "Named"

		payload = build_create_template_payload(self)
		payload.pop("name", None)
		payload.pop("language", None)
		logger.info("_update_in_meta | payload=%s", payload)

		ref_doctype, ref_docname = self._log_reference()

		try:
			logger.info("_update_in_meta | calling Meta API update_template...")
			result = whatsapp.update_template(self.whatsapp_template_id, payload)
			logger.info("_update_in_meta | Meta API response | result=%s", result)
		except Exception as e:
			logger.error("_update_in_meta | Meta API call failed | error=%s", e, exc_info=True)
			log(
				"Error",
				"Template",
				f"Failed to update template {self.template_label} in Meta: {e}",
				account=self.whatsapp_account,
				reference_doctype=ref_doctype,
				reference_docname=ref_docname,
				request_data=payload,
				traceback=frappe.get_traceback(),
			)
			frappe.throw(_("Failed to update template in Meta: {0}").format(str(e)))

		self.status = normalize_template_status(result.get("status", ""))
		logger.info("_update_in_meta | success | status=%s", self.status)
		log(
			"Info",
			"Template",
			f"Template {self.template_label} updated in Meta, status={self.status}",
			account=self.whatsapp_account,
			reference_doctype=ref_doctype,
			reference_docname=ref_docname,
			request_data=payload,
			response_data=result,
		)


def on_doctype_update():
	frappe.db.add_unique(
		"WhatsApp Template",
		["whatsapp_account", "template_name", "language"],
		constraint_name="unique_account_template_language",
	)


def normalize_string(s: str) -> str:
	normalized_label = re.sub(r"[^\w\s]", "_", s.strip())
	normalized_label = re.sub(r"\s+", "_", normalized_label)
	return normalized_label.lower()


def get_template_variables(s: str) -> list[str]:
	variables_list = re.findall(r"\{\{\s*([^}]+)\s*\}\}", s) if s else []
	if not s:
		return []
	return variables_list


def get_settings() -> WhatsAppSettings:
	return frappe.get_single("WhatsApp Settings").as_dict()


@frappe.whitelist()
def get_active_accounts() -> list[WhatsAppAccount]:
	accounts = frappe.get_all(
		"WhatsApp Account",
		filters={"status": "Active"},
		fields=["name", "account_name", "business_id"],
	)
	return [
		cast(
			WhatsAppAccount,
			{
				"name": acc.name,
				"account_name": acc.account_name,
				"business_id": acc.business_id,
			},
		)
		for acc in accounts
	]


def _get_whatsapp_client(account_name: str) -> WhatsApp:
	settings = get_settings()
	account = frappe.get_doc("WhatsApp Account", account_name)
	return WhatsApp(
		args=frappe._dict(
			business_id=account.business_id,
			app_id=account.app_id or "",
			access_token=account.get_password("access_token"),
			phone_number_id=account.phone_id,
			base_url=settings.whatsapp_api_url,
			api_version=settings.whatsapp_api_version,
			account_name=account_name,
		)
	)


def _iter_templates(whatsapp: WhatsApp) -> Iterator[dict]:
	cursor = None
	while True:
		params: dict = {"limit": 100}
		if cursor:
			params["after"] = cursor

		result = whatsapp.get_template_list(filters=params)
		yield from result.get("data", [])

		page_info = result.get("paging", {}).get("cursors", {})
		cursor = page_info.get("next")
		if not cursor:
			break


def _ensure_language(code: str) -> None:
	"""Meta adds languages between our releases, so an unknown code must not abort a sync."""
	if not code or frappe.db.exists("WhatsApp Language", code):
		return

	frappe.get_doc(
		doctype="WhatsApp Language",
		language_code=code,
		language_name=SUPPORTED_LANGUAGES.get(code, code),
	).insert(ignore_permissions=True)


def _upsert_template(template_data: dict, account_name: str) -> tuple[str, bool]:
	logger = frappe.logger("whatsapp", allow_site=True, max_size=10_485_760)

	category = template_data.get("category", "")
	if category == "SAMPLE":
		logger.warning(
			"Skipping SAMPLE template | name=%s id=%s",
			template_data.get("name"),
			template_data.get("id"),
		)
		return template_data.get("name", ""), False

	whatsapp_template_id = template_data.get("id", "")
	parsed = parse_whatsapp_template_to_doc(template_data)
	_ensure_language(parsed["language"])

	existing = frappe.get_all(
		"WhatsApp Template",
		filters={
			"template_name": parsed["template_name"],
			"language": parsed["language"],
			"whatsapp_account": account_name,
		},
		pluck="name",
		limit=1,
	)

	if existing:
		doc = frappe.get_doc("WhatsApp Template", existing[0])
		doc.flags.from_sync = True
		doc.whatsapp_account = account_name
		doc.status = parsed.get("status", "Pending")
		doc.template_type = parsed["template_type"]
		doc.header_type = parsed.get("header_type", "Text")
		doc.header_text = parsed.get("header_text", "")
		doc.header_media_handle = parsed.get("header_media_handle", "")
		doc.message = parsed.get("message", "")
		doc.footer = parsed.get("footer", "")
		doc.variable_format = parsed.get("variable_format", "Named")

		existing_variable_fields = {v.variable_name: v.variable_field for v in doc.template_variables}
		parsed_variables = parsed.get("template_variables", [])
		for pv in parsed_variables:
			pv["variable_field"] = existing_variable_fields.get(pv["variable_name"], "")
		doc.set("template_variables", parsed_variables)

		doc.set("buttons", parsed.get("buttons", []))
		if whatsapp_template_id and not doc.whatsapp_template_id:
			doc.whatsapp_template_id = whatsapp_template_id
		doc.save()
		log(
			"Info",
			"Template",
			f"Synced existing template {parsed['template_name']} (status={parsed.get('status')})",
			account=account_name,
			reference_doctype="WhatsApp Template",
			reference_docname=doc.name,
		)
		return parsed["template_name"], False

	doc = frappe.get_doc(
		{
			"doctype": "WhatsApp Template",
			"template_label": parsed["template_name"],
			"template_name": parsed["template_name"],
			"whatsapp_account": account_name,
			"whatsapp_template_id": whatsapp_template_id,
			"status": parsed.get("status", "Pending"),
			"template_type": parsed["template_type"],
			"language": parsed["language"],
			"header_type": parsed.get("header_type", "Text"),
			"header_text": parsed.get("header_text", ""),
			"header_media_handle": parsed.get("header_media_handle", ""),
			"message": parsed.get("message", ""),
			"footer": parsed.get("footer", ""),
			"variable_format": parsed.get("variable_format", "Named"),
			"template_variables": parsed.get("template_variables", []),
			"buttons": parsed.get("buttons", []),
		}
	)
	doc.insert()
	log(
		"Info",
		"Template",
		f"Created new template {parsed['template_name']} from sync (status={parsed.get('status')})",
		account=account_name,
		reference_doctype="WhatsApp Template",
		reference_docname=doc.name,
	)
	return parsed["template_name"], True


def _mark_deleted_templates(meta_variants: set[tuple[str, str]], account_name: str | None = None) -> None:
	local_templates = frappe.get_all(
		"WhatsApp Template",
		filters={"whatsapp_account": account_name},
		fields=["name", "template_name", "language"],
	)
	for local in local_templates:
		if (local.template_name, local.language) not in meta_variants:
			frappe.db.set_value("WhatsApp Template", local.name, "status", "Deleted")
			log(
				"Info",
				"Template",
				f"Template {local.template_name} ({local.language}) marked as Deleted (not found in Meta)",
				reference_doctype="WhatsApp Template",
				reference_docname=local.name,
				account=account_name,
			)


@frappe.whitelist()
def sync_from_account(account_name: str) -> dict:
	whatsapp = _get_whatsapp_client(account_name)

	synced = []
	skipped = []
	meta_variants: set[tuple[str, str]] = set()

	for template_data in _iter_templates(whatsapp):
		meta_variants.add((template_data.get("name", ""), template_data.get("language", "")))
		name, is_new = _upsert_template(template_data, account_name)
		if is_new:
			synced.append(name)
		else:
			skipped.append(name)

	_mark_deleted_templates(meta_variants, account_name)
	frappe.db.commit()

	log(
		"Info",
		"Template",
		f"Sync completed for account {account_name}: {len(synced)} new, {len(skipped)} updated",
		account=account_name,
	)

	return {
		"synced": synced,
		"skipped": skipped,
		"total_synced": len(synced),
		"total_skipped": len(skipped),
	}


@frappe.whitelist()
def get_doctype_columns(doctype: str) -> list[str]:
	frappe.has_permission(doctype, "read", throw=True)
	meta = frappe.get_meta(doctype)
	return [
		df.fieldname for df in meta.fields if df.fieldtype in ("Data", "Link", "Select", "Small Text", "Text")
	]


@frappe.whitelist()
def create_template_and_push(doc_data: dict, account_name: str) -> dict:
	run_access_guards()

	existing_name = doc_data.get("name")
	is_new = doc_data.get("__islocal", True)

	if is_new or not existing_name:
		doc = frappe.new_doc("WhatsApp Template")
		doc.update(doc_data)
	else:
		doc = frappe.get_doc("WhatsApp Template", existing_name)
		if doc.whatsapp_template_id:
			frappe.throw(
				_(
					"Template '{0}' already exists on Meta (ID: {1}). "
					"Clear the WhatsApp Template ID to re-push, "
					"or edit on WhatsApp Manager and sync."
				).format(doc.template_label, doc.whatsapp_template_id)
			)
		doc.update(doc_data)

	doc.whatsapp_account = account_name

	whatsapp = _get_whatsapp_client(account_name)

	payload = build_create_template_payload(doc)
	try:
		result = whatsapp.create_template(payload)
	except Exception as e:
		log(
			"Error",
			"Template",
			f"Failed to create and push template: {e}",
			account=account_name,
			request_data=payload,
			traceback=frappe.get_traceback(),
		)
		frappe.throw(_("Failed to push template to Meta: {0}").format(str(e)))

	template_id = result.get("id", None)
	if not template_id:
		log(
			"Error",
			"Template",
			"Meta API returned no template ID during create_and_push",
			account=account_name,
			request_data=payload,
			response_data=result,
		)
		frappe.throw(_("Meta API did not return a template ID"))

	doc.whatsapp_template_id = template_id
	doc.status = normalize_template_status(result.get("status", ""))

	if is_new or not existing_name:
		doc.insert()
	else:
		doc.save()

	log(
		"Info",
		"Template",
		f"Created and pushed template {doc.template_label}, id={template_id}, status={doc.status}",
		account=account_name,
		reference_doctype="WhatsApp Template",
		reference_docname=doc.name,
		request_data=payload,
		response_data=result,
	)

	return {"name": doc.name, "whatsapp_template_id": template_id}


@frappe.whitelist()
def get_sendable_templates(reference_doctype: str) -> list[dict]:
	"""Return Approved templates that can be sent from the given DocType.

	Sendable means bound to that doctype, or unbound with no variables. Unbound templates
	with variables have nothing to resolve them from (see DESIGN_DECISIONS.md).
	"""
	run_access_guards()

	templates = frappe.get_all(
		"WhatsApp Template",
		filters={
			"status": "Approved",
			"reference_doctype": ["in", [reference_doctype, ""]],
		},
		fields=[
			"name",
			"template_label",
			"template_name",
			"message",
			"footer",
			"header_text",
			"header_type",
			"reference_doctype",
			"language",
		],
		order_by="modified desc",
	)
	if not templates:
		return []

	unbound_names = [t.name for t in templates if not t.reference_doctype]
	unbound_with_vars: set[str] = set()
	if unbound_names:
		unbound_with_vars = {
			row.parent
			for row in frappe.get_all(
				"Template Variable",
				filters={"parent": ["in", unbound_names], "parenttype": "WhatsApp Template"},
				fields=["parent"],
			)
		}

	sendable = [t for t in templates if t.name not in unbound_with_vars]
	if not sendable:
		return []

	# A child table needs its own query: frappe.get_all on the parent cannot return one,
	# whatever is in the field list.
	buttons_by_template: dict[str, list[dict]] = {}
	for row in frappe.get_all(
		"WhatsApp Template Button",
		filters={"parent": ["in", [t.name for t in sendable]], "parenttype": "WhatsApp Template"},
		fields=["parent", "button_type", "button_text", "url", "phone_number"],
		order_by="idx asc",
	):
		buttons_by_template.setdefault(row.parent, []).append(
			{
				"button_type": row.button_type,
				"button_text": row.button_text,
				"url": row.url,
				"phone_number": row.phone_number,
			}
		)

	for template in sendable:
		template["buttons"] = buttons_by_template.get(template.name, [])

	return sendable


@frappe.whitelist()
def sync_all() -> dict:
	accounts = get_active_accounts()
	settings = get_settings()

	if not settings:
		log("Error", "Template", "Sync failed: WhatsApp Settings not found")
		frappe.throw(_("WhatsApp Settings not found. Please create a settings first."))

	if not accounts:
		log("Error", "Template", "Sync failed: No active WhatsApp accounts found")
		frappe.throw(_("No active WhatsApp accounts found. Please create an account first."))

	if len(accounts) == 1:
		return sync_from_account(accounts[0]["name"])

	log("Info", "Template", "Scheduled sync found multiple accounts, prompting user to select")
	frappe.msgprint(
		_("Multiple accounts found. Please select an account to sync from."),
		title=_("Select Account"),
	)
	return {"accounts": accounts}
