import frappe
from frappe.permissions import add_permission

LEVEL_ONE_READ = {"parent": "WA Message", "role": "System Manager", "permlevel": 1}


def execute():
	# A DocType with any Custom DocPerm ignores the permissions in its JSON, so hosts that
	# customised WA Message (CRM's add_roles does) never get the new level-1 read.
	if not frappe.db.exists("Custom DocPerm", {"parent": "WA Message"}):
		return
	if frappe.db.exists("Custom DocPerm", LEVEL_ONE_READ):
		return
	add_permission("WA Message", "System Manager", permlevel=1)
