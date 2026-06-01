import frappe


def execute():
	"""Capitalize existing WhatsApp Template status values.

	The `status` field options changed from all-caps (Meta's raw format) to
	capitalized words. Existing rows still hold the old all-caps values; map
	them in place to the new options.
	"""
	mapping = {
		"PENDING": "Pending",
		"APPROVED": "Approved",
		"REJECTED": "Rejected",
		"DELETED": "Deleted",
	}
	for old, new in mapping.items():
		frappe.db.set_value(
			"WhatsApp Template", {"status": old}, "status", new, update_modified=False
		)

	frappe.db.commit()
