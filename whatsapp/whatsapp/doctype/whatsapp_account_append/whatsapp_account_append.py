# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class WhatsAppAccountAppend(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		append_to: DF.Link | None
		message_field: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		sender_field: DF.Data | None
		sender_name_field: DF.Data | None
		timestamp_field: DF.Data | None
		trigger_on: DF.Literal["Incoming", "Outgoing", "Both"]
	# end: auto-generated types

	pass
