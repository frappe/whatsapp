# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

import re
from typing import cast

import frappe
from frappe import _
from frappe.model.document import Document

from whatsapp.whatsapp.doctype.whatsapp_account.whatsapp_account import WhatsappAccount
from whatsapp.whatsapp.doctype.whatsapp_setting.whatsapp_setting import WhatsappSetting


class WhatsappTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from whatsapp.whatsapp.doctype.template_variable.template_variable import TemplateVariable
		from whatsapp.whatsapp.doctype.whatsapp_account.whatsapp_account import WhatsappAccount
		from whatsapp.whatsapp.doctype.whatsapp_template_button.whatsapp_template_button import (
			WhatsappTemplateButton,
		)

		buttons: DF.Table[WhatsappTemplateButton]
		footer: DF.Data | None
		header_media: DF.Attach | None
		header_media_handle: DF.Data | None
		header_text: DF.Data | None
		header_type: DF.Literal["TEXT", "IMAGE", "DOCUMENT", "GIF", "VIDEO"]
		language: DF.Literal["en_UK", "en_US", "en"]
		message: DF.Code
		reference_doctype: DF.Link | None
		status: DF.Literal["PENDING", "APPROVED", "REJECTED", "DELETED"]
		template_label: DF.Data
		template_name: DF.Data | None
		template_type: DF.Literal["UTILITY", "MARKETING", "AUTHENTICATION"]
		template_variables: DF.Table[TemplateVariable]
		variable_format: DF.Literal["named", "positional"]
		whatsapp_account: DF.Link | None
		whatsapp_template_id: DF.Data | None
	# end: auto-generated types

	def validate_template_variables(self) -> None:
		if self.header_text and self.header_type == "TEXT":
			header_variables = get_template_variables(self.header_text)
		else:
			header_variables = []

		body_variables = get_template_variables(self.message)

		variables = [*header_variables, *body_variables]

		if len(variables) != len(self.template_variables):
			frappe.throw(
				"Number of template variables in table does not match the number of variables in the message"
			)

		for variable in self.template_variables:
			if variable.variable_name not in variables:
				frappe.throw(f"Variable {variable.variable_name} not found in message")

	def validate_template_name(self) -> None:
		if not self.template_name:
			frappe.throw("Template name is required")
			return

		if len(self.template_name) > 512:
			frappe.throw("Template name should not exceed 512 characters")

		if not re.match(r"^[a-zA-Z0-9_]+$", self.template_name):
			frappe.throw("Template name should only contain alphanumeric characters and underscores")

	def on_validate(self):
		self.validate_template_variables()
		self.validate_template_name()

	def before_save(self):
		logger = frappe.logger("whatsapp", allow_site=True, max_size=10_485_760)
		logger.info(
			"before_save | template_label=%s template_name=%s whatsapp_template_id=%s __islocal=%s",
			self.template_label,
			self.template_name,
			self.whatsapp_template_id,
			self.get("__islocal"),
		)

		if not self.template_name:
			old = self.template_label
			self.template_name = normalize_string(self.template_label)
			logger.info("before_save | auto-generated template_name | old=%s new=%s", old, self.template_name)

		if not self.whatsapp_template_id:
			logger.info("before_save | no whatsapp_template_id, proceeding to push to Meta")
			self._push_to_meta()
		else:
			logger.info(
				"before_save | template already has whatsapp_template_id=%s, skipping push",
				self.whatsapp_template_id,
			)

	def _push_to_meta(self):
		logger = frappe.logger("whatsapp", allow_site=True, max_size=10_485_760)
		logger.info(
			"_push_to_meta | start | template_label=%s template_name=%s",
			self.template_label,
			self.template_name,
		)

		if not self.whatsapp_account:
			logger.error("_push_to_meta | whatsapp_account is not set")
			frappe.throw(_("WhatsApp Account is required to push template to Meta"))

		account = frappe.get_doc("Whatsapp Account", self.whatsapp_account)
		logger.info(
			"_push_to_meta | account=%s business_id=%s phone_id=%s",
			account.name,
			account.businesss_id,
			account.phone_id,
		)

		settings = get_settings()
		base_url = settings.whatsapp_api_url
		api_version = settings.whatsapp_api_version
		logger.info("_push_to_meta | settings | base_url=%s api_version=%s", base_url, api_version)

		from whatsapp.whatsapp.api.utils import build_create_template_payload
		from whatsapp.whatsapp.api.whatsapp import Whatsapp

		whatsapp = Whatsapp(
			args=frappe._dict(
				business_id=account.businesss_id,
				app_id="",
				access_token=account.access_token,
				phone_number_id=account.phone_id,
				base_url=base_url,
				api_version=api_version,
			)
		)

		if not self.variable_format:
			self.variable_format = "named"

		payload = build_create_template_payload(self)
		logger.info("_push_to_meta | payload=%s", payload)

		try:
			logger.info("_push_to_meta | calling Meta API create_template...")
			result = whatsapp.create_template(payload)
			logger.info("_push_to_meta | Meta API response | result=%s", result)
		except Exception as e:
			logger.error("_push_to_meta | Meta API call failed | error=%s", e, exc_info=True)
			frappe.throw(_("Failed to push template to Meta: {0}").format(str(e)))

		template_id = result.get("id")
		if not template_id:
			logger.error("_push_to_meta | Meta API returned no id | full_response=%s", result)
			frappe.throw(_("Meta API did not return a template ID"))

		self.whatsapp_template_id = template_id
		self.status = result.get("status", "PENDING")
		logger.info("_push_to_meta | success | whatsapp_template_id=%s status=%s", template_id, self.status)


def normalize_string(s: str) -> str:
	normalized_label = re.sub(r"[^\w\s]", "_", s.strip())
	normalized_label = re.sub(r"\s+", "_", normalized_label)
	return normalized_label.lower()


def get_template_variables(s: str) -> list[str]:
	variables_list = re.findall(r"\{\{\s*([^}]+)\s*\}\}", s) if s else []
	if not s:
		return []
	return variables_list


def get_settings() -> WhatsappSetting:
	return frappe.get_single("Whatsapp Setting").as_dict()


@frappe.whitelist()
def get_active_accounts() -> list[WhatsappAccount]:
	accounts = frappe.get_all(
		"Whatsapp Account",
		filters={"status": "Active"},
		fields=["name", "account_name", "businesss_id"],
	)
	return [
		cast(
			WhatsappAccount,
			{
				"name": acc.name,
				"account_name": acc.account_name,
				"business_id": acc.businesss_id,
			},
		)
		for acc in accounts
	]


@frappe.whitelist()
def sync_from_account(account_name: str) -> dict:
	account = frappe.get_doc("Whatsapp Account", account_name)
	settings = get_settings()

	from whatsapp.whatsapp.api.whatsapp import Whatsapp

	whatsapp = Whatsapp(
		args=frappe._dict(
			business_id=account.businesss_id,
			app_id="",
			access_token=account.access_token,
			phone_number_id=account.phone_id,
			base_url=settings.whatsapp_api_url,
			api_version=settings.whatsapp_api_version,
		)
	)

	skipped = []
	synced = []
	all_templates = []
	cursor = None

	while True:
		params = {"limit": 100}
		if cursor:
			params["after"] = cursor

		result = whatsapp.get_template_list(filters=params)
		templates = result.get("data", [])
		all_templates.extend(templates)

		page_info = result.get("paging", {}).get("cursors", {})
		cursor = page_info.get("next")
		if not cursor:
			break

	for template_data in all_templates:
		template_name = template_data.get("name")
		whatsapp_template_id = template_data.get("id", "")

		existing = frappe.get_all(
			"Whatsapp Template",
			filters={"template_name": template_name},
			pluck="name",
			limit=1,
		)

		from whatsapp.whatsapp.api.utils import parse_whatsapp_template_to_doc

		parsed = parse_whatsapp_template_to_doc(template_data)

		if existing:
			doc = frappe.get_doc("Whatsapp Template", existing[0])
			doc.status = parsed.get("status", "PENDING")
			doc.template_type = parsed["template_type"]
			doc.header_type = parsed.get("header_type", "TEXT")
			doc.header_text = parsed.get("header_text", "")
			doc.header_media_handle = parsed.get("header_media_handle", "")
			doc.message = parsed.get("message", "")
			doc.footer = parsed.get("footer", "")
			doc.variable_format = parsed.get("variable_format", "named")
			doc.set("template_variables", parsed.get("template_variables", []))
			doc.set("buttons", parsed.get("buttons", []))
			if whatsapp_template_id and not doc.whatsapp_template_id:
				doc.whatsapp_template_id = whatsapp_template_id
			doc.save()
			skipped.append(template_name)
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Whatsapp Template",
				"template_label": f"{parsed['template_name']} - {parsed['language']}",
				"template_name": parsed["template_name"],
				"whatsapp_template_id": whatsapp_template_id,
				"status": parsed.get("status", "PENDING"),
				"template_type": parsed["template_type"],
				"language": parsed["language"],
				"header_type": parsed.get("header_type", "TEXT"),
				"header_text": parsed.get("header_text", ""),
				"header_media_handle": parsed.get("header_media_handle", ""),
				"message": parsed.get("message", ""),
				"footer": parsed.get("footer", ""),
				"variable_format": parsed.get("variable_format", "named"),
				"template_variables": parsed.get("template_variables", []),
				"buttons": parsed.get("buttons", []),
			}
		)
		doc.insert()
		synced.append(template_name)

	_templates_in_meta = {t.get("name") for t in all_templates}

	local_templates = frappe.get_all(
		"Whatsapp Template",
		fields=["name", "template_name"],
	)
	for local in local_templates:
		if local.template_name not in _templates_in_meta:
			frappe.db.set_value("Whatsapp Template", local.name, "status", "DELETED")

	frappe.db.commit()

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
	from whatsapp.whatsapp.api.utils import build_create_template_payload
	from whatsapp.whatsapp.api.whatsapp import Whatsapp

	existing_name = doc_data.get("name")
	is_new = doc_data.get("__islocal", True)

	if is_new or not existing_name:
		doc = frappe.new_doc("Whatsapp Template")
		doc.update(doc_data)
	else:
		doc = frappe.get_doc("Whatsapp Template", existing_name)
		if doc.whatsapp_template_id:
			frappe.throw(
				_(
					"Template '{0}' already exists on Meta (ID: {1}). "
					"Clear the WhatsApp Template ID to re-push, "
					"or edit on WhatsApp Manager and sync."
				).format(doc.template_label, doc.whatsapp_template_id)
			)
		doc.update(doc_data)

	account = frappe.get_doc("Whatsapp Account", account_name)
	settings = get_settings()

	whatsapp = Whatsapp(
		args=frappe._dict(
			business_id=account.businesss_id,
			app_id="",
			access_token=account.access_token,
			phone_number_id=account.phone_id,
			base_url=settings.whatsapp_api_url,
			api_version=settings.whatsapp_api_version,
		)
	)

	payload = build_create_template_payload(doc)
	try:
		result = whatsapp.create_template(payload)
	except Exception as e:
		frappe.throw(_("Failed to push template to Meta: {0}").format(str(e)))

	template_id = result.get("id")
	if not template_id:
		frappe.throw(_("Meta API did not return a template ID"))

	doc.whatsapp_template_id = template_id
	doc.status = result.get("status", "PENDING")

	if is_new or not existing_name:
		doc.insert()
	else:
		doc.save()

	return {"name": doc.name, "whatsapp_template_id": template_id}


@frappe.whitelist()
def sync_all() -> dict:
	accounts = get_active_accounts()
	settings = get_settings()

	if not settings:
		frappe.throw(_("Whatsapp Settings not found. Please create a settings first."))

	if not accounts:
		frappe.throw(_("No active WhatsApp accounts found. Please create an account first."))

	if len(accounts) == 1:
		return sync_from_account(accounts[0]["name"])

	frappe.msgprint(
		_("Multiple accounts found. Please select an account to sync from."),
		title=_("Select Account"),
	)
	return {"accounts": accounts}
