import frappe


def execute():
	frappe.db.set_value("WA Profile", {"status": "Archived"}, "status", "Disabled", update_modified=False)
