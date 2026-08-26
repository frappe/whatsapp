import frappe


def execute():
	"""Point `WhatsApp Settings.default_account` at the only account, where there is one.

	A default is now set automatically when the first account is created, so a
	single-account site never has to pick one. Existing sites created before that
	may have one account and no default, which leaves WhatsApp switched off in CRM
	(crm.api.whatsapp.is_whatsapp_enabled requires a default). Fill it in.
	"""
	if frappe.db.get_single_value("WhatsApp Settings", "default_account"):
		return

	accounts = frappe.get_all("WhatsApp Account", pluck="name", limit=2)
	if len(accounts) == 1:
		frappe.db.set_single_value("WhatsApp Settings", "default_account", accounts[0])
