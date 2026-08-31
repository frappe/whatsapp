import frappe

from whatsapp.whatsapp.api.languages import RETIRED_LANGUAGE_CODES


def execute():
	"""`en_UK` was offered in the old Select options but Meta never accepted it."""
	for old, new in RETIRED_LANGUAGE_CODES.items():
		frappe.db.set_value("WhatsApp Template", {"language": old}, "language", new, update_modified=False)

	frappe.db.commit()
