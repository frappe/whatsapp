# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class TemplateVariable(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		variable_example: DF.Data
		variable_field: DF.Data | None
		variable_name: DF.Data
	# end: auto-generated types

	pass
