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

		from whatsapp.whatsapp.doctype.whatsapp_account_append.whatsapp_account_append import (
			WhatsappAccountAppend,
		)

		access_token: DF.LongText | None
		account_name: DF.Data | None
		append_actions: DF.Table[WhatsappAccountAppend]
		app_id: DF.Data | None
		business_id: DF.Data | None
		phone_id: DF.Data | None
		status: DF.Literal["Active", "Inactive"]
	# end: auto-generated types

	pass
