# Copyright (c) 2026, pratham@frappe.io and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WhatsappAccount(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		access_token: DF.Data | None
		account_name: DF.Data | None
		businesss_id: DF.Data | None
		phone_id: DF.Data | None
		status: DF.Literal["Active", "Inactive"]
	# end: auto-generated types

	pass
