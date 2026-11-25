# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

"""Which fields of a DocType can hold a mapped value. Shared by Append Actions and Flow buttons."""

import frappe
from frappe import _
from frappe.model import data_fieldtypes

TEXT = ("Data", "Small Text", "Text", "Long Text", "Text Editor", "Markdown Editor")
LONG_TEXT = ("Small Text", "Text", "Long Text", "Text Editor", "Markdown Editor")
NUMBER = ("Int", "Float", "Currency", "Percent")
DOCTYPE_LINK = "Link to DocType"
STRING = (*TEXT, "Select", "Link", "Phone")
WHOLE_JSON = ("JSON", "Code", "Long Text")

# What a Flow response or the incoming message can write into, by the type of the source.
SOURCE_FIELD_TYPES = {
	"string": STRING,
	"sender_phone": STRING,
	"sender_name": STRING,
	"number": (*NUMBER, *TEXT),
	"date": ("Date", "Datetime", *TEXT),
	"boolean": ("Check", *TEXT),
	"array": ("Table MultiSelect", *LONG_TEXT),
	"object": WHOLE_JSON,
	"whole_response": WHOLE_JSON,
	"media": ("Attach", "Attach Image"),
	"reference_doctype": (DOCTYPE_LINK, "Data"),
	"reference_name": ("Dynamic Link", "Link", "Data"),
	"received_at": ("Datetime", "Date", "Data"),
	"unknown": data_fieldtypes,
}

# What can fill a Flow input, by the type its entry screen declares. Object and array inputs are out of scope.
INPUT_FIELD_TYPES = {
	"string": (*TEXT, "Select", "Link", "Date", "Datetime", "Phone"),
	"number": NUMBER,
	"boolean": ("Check",),
	"unknown": data_fieldtypes,
}


@frappe.whitelist()
def get_mappable_fields(target_doctype: str = "", source_type: str = "", txt: str = "") -> list[dict]:
	"""Fields on `target_doctype` that can hold a source of `source_type` (a key of SOURCE_FIELD_TYPES)."""
	frappe.has_permission("WA Template", "write", throw=True)

	if not target_doctype or source_type not in SOURCE_FIELD_TYPES:
		return []

	frappe.has_permission(target_doctype, "read", throw=True)
	return field_options(target_doctype, SOURCE_FIELD_TYPES[source_type], txt)


@frappe.whitelist()
def get_input_source_fields(
	reference_doctype: str = "", declared_type: str = "", txt: str = ""
) -> list[dict]:
	"""Fields on `reference_doctype` that can fill a Flow input declared as `declared_type` (a key of INPUT_FIELD_TYPES)."""
	frappe.has_permission("WA Template", "write", throw=True)

	if not reference_doctype or declared_type not in INPUT_FIELD_TYPES:
		return []

	frappe.has_permission(reference_doctype, "read", throw=True)
	return field_options(reference_doctype, INPUT_FIELD_TYPES[declared_type], txt)


def field_options(target_doctype: str, fieldtypes: tuple[str, ...], txt: str = "") -> list[dict]:
	txt = (txt or "").lower()
	return [
		{
			"value": df.fieldname,
			"label": df.fieldname,
			"description": f"{_(df.label)} ({df.fieldtype})" if df.label else df.fieldtype,
		}
		for df in frappe.get_meta(target_doctype).fields
		if accepts(df, fieldtypes) and (txt in df.fieldname.lower() or txt in (df.label or "").lower())
	]


def validate_mapped_field(target_meta, fieldname: str, fieldtypes: tuple[str, ...], where: str, label: str):
	"""Throw unless `fieldname` exists on the target and can hold a value for `fieldtypes`."""
	df = target_meta.get_field(fieldname)

	if not df:
		frappe.throw(
			_("{0}: {1} '{2}' does not exist on {3}").format(where, label, fieldname, target_meta.name)
		)

	if not accepts(df, fieldtypes):
		frappe.throw(
			_("{0}: {1} '{2}' is a {3} field; {1} must be one of {4}").format(
				where, label, fieldname, df.fieldtype, ", ".join(fieldtypes)
			)
		)


def validate_list_doctype(target_meta, where: str) -> None:
	"""Throw for a child table or single, which has no list to add a document to."""
	if target_meta.istable or target_meta.issingle:
		frappe.throw(
			_("{0}: cannot append to {1}; a child table or single has no list to add to").format(
				where, target_meta.name
			)
		)


def accepts(df, fieldtypes: tuple[str, ...]) -> bool:
	if df.fieldtype == "Link" and df.options == "DocType" and DOCTYPE_LINK in fieldtypes:
		return True
	return df.fieldtype in fieldtypes
