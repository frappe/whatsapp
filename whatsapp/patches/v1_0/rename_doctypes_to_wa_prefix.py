import frappe

# Child tables first so each parent's Table options are already updated when the
# parent's meta is loaded during its own rename.
DOCTYPE_RENAMES = [
	("WhatsApp Account Append", "WA Account Append"),
	("WhatsApp Message Interactive Button", "WA Message Interactive Button"),
	("WhatsApp Message List Item", "WA Message List Item"),
	("WhatsApp Template Button", "WA Template Button"),
	("Template Variable", "WA Template Variable"),
	("WhatsApp Language", "WA Language"),
	("WhatsApp Log", "WA Log"),
	("WhatsApp Account", "WA Account"),
	("WhatsApp Profile", "WA Profile"),
	("WhatsApp Template", "WA Template"),
	("WhatsApp Message", "WA Message"),
	("WhatsApp Settings", "WA Settings"),
]


def execute():
	for old, new in DOCTYPE_RENAMES:
		if frappe.db.exists("DocType", old) and not frappe.db.exists("DocType", new):
			frappe.rename_doc("DocType", old, new, force=True)
	frappe.clear_cache()
