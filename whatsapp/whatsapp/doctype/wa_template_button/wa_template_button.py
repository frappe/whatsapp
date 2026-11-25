# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WATemplateButton(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		button_text: DF.Data
		button_type: DF.Literal["Quick Reply", "Copy Code", "URL", "Voice Call", "Phone Number", "Flow"]
		flow: DF.Link | None
		flow_action: DF.Literal["Navigate", "Data Exchange"]
		flow_icon: DF.Literal["", "Document", "Promotion", "Review"]
		flow_inputs: DF.JSON | None
		flow_response_actions: DF.JSON | None
		flow_screen: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		phone_number: DF.Data | None
		url: DF.Data | None
	# end: auto-generated types

	pass
