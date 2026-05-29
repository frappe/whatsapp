import frappe

DOCTYPE_RENAMES = [
	("Whatsapp Account", "WhatsApp Account"),
	("Whatsapp Account Append", "WhatsApp Account Append"),
	("Whatsapp Log", "WhatsApp Log"),
	("Whatsapp Message", "WhatsApp Message"),
	("Whatsapp Message Interactive Button", "WhatsApp Message Interactive Button"),
	("Whatsapp Message List Item", "WhatsApp Message List Item"),
	("Whatsapp Profile", "WhatsApp Profile"),
	("Whatsapp Template", "WhatsApp Template"),
	("Whatsapp Template Button", "WhatsApp Template Button"),
	("Whatsapp Setting", "WhatsApp Settings"),
]


def _binary_exists(doctype, name):
	rows = frappe.db.sql(
		f"SELECT 1 FROM `tab{doctype}` WHERE BINARY name = %s LIMIT 1", (name,)
	)
	return bool(rows)


def _binary_table_name(table_name):
	rows = frappe.db.sql(
		"SELECT table_name FROM information_schema.tables "
		"WHERE table_schema=DATABASE() AND LOWER(table_name)=LOWER(%s) LIMIT 1",
		(table_name,),
	)
	return rows[0][0] if rows else None


def _rename_table_case_only(old_table, new_table):
	"""Rename a table via an intermediate name so MySQL with lower_case_table_names != 0
	actually changes the stored case on disk."""
	tmp = old_table + "__RenamingTmp"
	frappe.db.sql_ddl(f"RENAME TABLE `{old_table}` TO `{tmp}`")
	frappe.db.sql_ddl(f"RENAME TABLE `{tmp}` TO `{new_table}`")


def execute():
	# Module Def: framework rejects renaming non-custom modules, so flip `custom`
	# temporarily and use an intermediate name (case-insensitive MySQL otherwise no-ops the rename).
	if _binary_exists("Module Def", "Whatsapp") and not _binary_exists("Module Def", "WhatsApp"):
		frappe.db.set_value("Module Def", "Whatsapp", "custom", 1, update_modified=False)
		frappe.db.commit()
		frappe.rename_doc("Module Def", "Whatsapp", "WhatsAppRenamingTmp", force=True)
		frappe.rename_doc("Module Def", "WhatsAppRenamingTmp", "WhatsApp", force=True)
		frappe.db.set_value("Module Def", "WhatsApp", "custom", 0, update_modified=False)
		frappe.db.commit()

	for old, new in DOCTYPE_RENAMES:
		# Step 1: rename the DocType record itself, via an intermediate name so the
		# underlying table rename actually triggers on case-insensitive MySQL.
		if _binary_exists("DocType", old) and not _binary_exists("DocType", new):
			intermediate = old.replace(" ", "") + "RenamingTmp"
			frappe.rename_doc("DocType", old, intermediate, force=True)
			frappe.db.commit()
			frappe.rename_doc("DocType", intermediate, new, force=True)
			frappe.db.commit()

		# Step 2: fix the table case if the DocType is already renamed but the
		# underlying table is still stored with the old case (e.g. from a prior
		# partial migration attempt). Single doctypes have no table to fix.
		meta = frappe.get_meta(new) if _binary_exists("DocType", new) else None
		if meta and not meta.issingle and not meta.is_virtual:
			expected = f"tab{new}"
			actual = _binary_table_name(expected)
			if actual and actual != expected:
				_rename_table_case_only(actual, expected)
				frappe.db.commit()

	frappe.clear_cache()
