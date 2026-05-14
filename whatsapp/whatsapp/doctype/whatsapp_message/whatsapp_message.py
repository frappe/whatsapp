# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WhatsappMessage(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		is_template: DF.Check
		message: DF.LongText | None
		template_body_parameters: DF.Code | None
		template_header_parameters: DF.Code | None
		to: DF.Data | None
		whatsapp_account: DF.Link | None
		whatsapp_template: DF.Link | None
	# end: auto-generated types

	pass
