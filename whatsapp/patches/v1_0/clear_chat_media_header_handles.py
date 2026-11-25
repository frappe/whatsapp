import frappe


def execute():
	"""Sends used to cache a chat media id in `header_media_handle`, which Meta rejects as an approval
	handle. Clear it on templates with a local sample so the next push uploads a real one."""
	frappe.db.set_value(
		"WA Template",
		{"header_media": ("is", "set"), "header_media_handle": ("is", "set")},
		"header_media_handle",
		None,
		update_modified=False,
	)
