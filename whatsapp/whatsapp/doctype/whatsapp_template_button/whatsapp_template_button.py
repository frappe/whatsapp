# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WhatsAppTemplateButton(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		button_text: DF.Data
		button_type: DF.Literal["QUICK_REPLY", "COPY_CODE", "URL", "VOICE_CALL", "PHONE_NUMBER"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		phone_number: DF.Data | None
		url: DF.Data | None
	# end: auto-generated types

	pass
