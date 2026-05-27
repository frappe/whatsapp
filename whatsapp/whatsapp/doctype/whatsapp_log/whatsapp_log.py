# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WhatsappLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		account: DF.Link | None
		event_type: DF.Literal["", "Webhook", "Template", "Message", "API", "System"]
		level: DF.Literal["Info", "Warning", "Error", "Debug"]
		message: DF.Text
		reference_docname: DF.DynamicLink | None
		reference_doctype: DF.Link | None
		request_data: DF.Code | None
		response_data: DF.Code | None
		timestamp: DF.Datetime | None
		traceback: DF.Code | None
	# end: auto-generated types

	pass
