# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class WhatsAppAccountAppend(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		append_to: DF.Link
		message_field: DF.Autocomplete | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		sender_field: DF.Autocomplete
		sender_name_field: DF.Autocomplete
		timestamp_field: DF.Autocomplete | None
		trigger_on: DF.Literal["Incoming", "Outgoing", "Both"]
	# end: auto-generated types

	pass
