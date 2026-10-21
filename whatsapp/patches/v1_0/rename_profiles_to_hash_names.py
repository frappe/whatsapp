import re

import frappe

HASH_NAME = re.compile(r"^[0-9a-f]{10}$")


def execute():
	"""Profiles were named after the sender's display name, which one person messaging
	two accounts, or two people sharing a name, both collide on. Every existing profile
	takes the hash name new ones get; rename_doc carries its messages, logs and links."""
	for name in frappe.get_all("WA Profile", pluck="name"):
		if HASH_NAME.match(name):
			continue
		frappe.rename_doc(
			"WA Profile",
			name,
			frappe.generate_hash(length=10),
			force=True,
			show_alert=False,
			rebuild_search=False,
		)
