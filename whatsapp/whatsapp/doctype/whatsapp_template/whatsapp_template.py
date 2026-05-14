# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document


class WhatsappTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from whatsapp.whatsapp.doctype.template_variable.template_variable import (
			TemplateVariable,
		)
		from whatsapp.whatsapp.doctype.whatsapp_template_button.whatsapp_template_button import (
			WhatsappTemplateButton,
		)

		buttons: DF.Table[WhatsappTemplateButton]
		footer: DF.Data | None
		header_media: DF.Attach | None
		header_text: DF.Data | None
		header_type: DF.Literal["TEXT", "IMAGE", "DOCUMENT", "GIF", "VIDEO"]
		language: DF.Literal["en_UK", "en_US"]
		message: DF.Code
		related_doctype: DF.Link | None
		template_label: DF.Data
		template_name: DF.Data | None
		template_type: DF.Literal["UTILITY", "MARKETING", "AUTHENTICATION"]
		template_variables: DF.Table[TemplateVariable]
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
			frappe.throw(
				"Template name should only contain alphanumeric characters and underscores"
			)

	def on_validate(self):
		self.validate_template_variables()
		self.validate_template_name()

	def before_save(self):
		# make sure template_name is set before saving
		if not self.template_name:
			self.template_name = normalize_string(self.template_label)


def normalize_string(s: str) -> str:
	normalized_label = re.sub(r"[^\w\s]", "_", s.strip())
	normalized_label = re.sub(r"\s+", "_", normalized_label)
	return normalized_label.lower()


def get_template_variables(s: str) -> list[str]:
	variables_list = re.findall(r"\{\{\s*([^}]+)\s*\}\}", s) if s else []
	if not s:
		return []
	return variables_list


@frappe.whitelist()
def fetch() -> None:
	# TODO: To Be Implemented
	pass
