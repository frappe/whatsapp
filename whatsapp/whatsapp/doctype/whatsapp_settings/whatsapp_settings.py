# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WhatsappSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		whatsapp_api_url: DF.Data | None
		whatsapp_api_version: DF.Data | None
	# end: auto-generated types

	pass
