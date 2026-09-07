import frappe

from whatsapp.whatsapp.api.utils import BUTTON_TYPES, HEADER_TYPES, TEMPLATE_TYPES

VARIABLE_FORMATS = {"named": "Named", "positional": "Positional"}

FIELD_MAPPINGS = (
	("WhatsApp Template", "template_type", TEMPLATE_TYPES),
	("WhatsApp Template", "header_type", HEADER_TYPES),
	("WhatsApp Template", "variable_format", VARIABLE_FORMATS),
	("WhatsApp Template Button", "button_type", BUTTON_TYPES),
)


def execute():
	"""Rewrite template enum values from Meta's all-caps spelling to the Title Case options.

	Follows capitalize_template_status, which did the same for `status`.
	"""
	for doctype, fieldname, mapping in FIELD_MAPPINGS:
		for old, new in mapping.items():
			if old == new:
				continue
			frappe.db.set_value(doctype, {fieldname: old}, fieldname, new, update_modified=False)

	frappe.db.commit()
