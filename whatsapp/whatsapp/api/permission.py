import frappe


def has_app_permission() -> bool:
	return bool(frappe.has_permission("WA Settings"))
