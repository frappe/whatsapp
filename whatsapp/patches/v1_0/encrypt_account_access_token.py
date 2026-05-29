import frappe


def execute():
	"""Move plaintext WhatsApp Account access tokens into the encrypted __Auth store.

	The `access_token` field was changed from Long Text to Password. Existing rows
	still hold the plaintext value in the column; we re-save each doc so Frappe
	writes the value into `__Auth` and masks the column.
	"""
	rows = frappe.db.sql(
		"""
		SELECT name, access_token
		FROM `tabWhatsApp Account`
		WHERE access_token IS NOT NULL AND access_token != ''
		""",
		as_dict=True,
	)
	for row in rows:
		# Skip rows already masked (only '*' characters) — those tokens already live in __Auth.
		if set(row.access_token) == {"*"}:
			continue
		doc = frappe.get_doc("WhatsApp Account", row.name)
		doc.access_token = row.access_token
		doc.save(ignore_permissions=True)

	frappe.db.commit()
