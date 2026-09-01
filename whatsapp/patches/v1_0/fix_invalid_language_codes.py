import frappe

from whatsapp.whatsapp.api.languages import RETIRED_LANGUAGE_CODES


def execute():
	"""`en_UK` was offered in the old Select options but Meta never accepted it.

	A site can hold both an `en_UK` and an `en_GB` template for the same account and
	name. Renaming the code on both would clash with the new unique index on
	(whatsapp_account, template_name, language) and stop the migration, so where the
	`en_GB` template is already there the `en_UK` one is dropped and any message that
	pointed at it is moved over to the one that stays.
	"""
	for old, new in RETIRED_LANGUAGE_CODES.items():
		for template in frappe.get_all(
			"WhatsApp Template",
			filters={"language": old},
			fields=["name", "whatsapp_account", "template_name"],
		):
			existing = frappe.db.get_value(
				"WhatsApp Template",
				{
					"whatsapp_account": template.whatsapp_account,
					"template_name": template.template_name,
					"language": new,
				},
			)
			if not existing:
				frappe.db.set_value(
					"WhatsApp Template", template.name, "language", new, update_modified=False
				)
				continue

			frappe.db.set_value(
				"WhatsApp Message",
				{"whatsapp_template": template.name},
				"whatsapp_template",
				existing,
				update_modified=False,
			)
			frappe.delete_doc("WhatsApp Template", template.name, force=True, ignore_permissions=True)
