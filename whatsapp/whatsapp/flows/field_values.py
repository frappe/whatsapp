# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

"""Convert a Flow answer or a message detail to the value a target field holds."""

import json
from datetime import UTC, date, datetime

import frappe
from frappe.utils import convert_utc_to_system_timezone

from whatsapp.whatsapp.mapping import SOURCE_FIELD_TYPES, STRING


class UnconvertibleValue(Exception):
	pass


def to_field_value(df, value):
	"""Raise UnconvertibleValue when the field cannot hold the value."""
	if df.fieldtype in ATTACH:
		raise UnconvertibleValue(
			f"{df.fieldname} is skipped: uploaded media is not downloaded from Meta yet (media ID {value})"
		)
	converter = CONVERTERS.get(df.fieldtype)
	if not converter:
		return value
	try:
		return converter(df, value)
	except (ValueError, TypeError) as e:
		raise UnconvertibleValue(
			f"{df.fieldname} is skipped: {value!r} is not a valid {df.fieldtype} value ({e})"
		) from e


def _check(df, value) -> int:
	if isinstance(value, bool):
		return int(value)
	if isinstance(value, str) and value.lower() in ("true", "false"):
		return int(value.lower() == "true")
	raise ValueError("expected a boolean")


def _int(df, value) -> int:
	number = _float(df, value)
	if not number.is_integer():
		raise ValueError("expected a whole number")
	return int(number)


def _float(df, value) -> float:
	if isinstance(value, bool) or not isinstance(value, int | float | str):
		raise TypeError("expected a number")
	return float(value)


def _date(df, value) -> date:
	if isinstance(value, datetime):
		return value.date()
	return _datetime(df, value).date()


def _datetime(df, value) -> datetime:
	if isinstance(value, datetime):
		return value
	parsed = datetime.fromisoformat(value)
	if parsed.tzinfo:
		parsed = convert_utc_to_system_timezone(parsed.astimezone(UTC)).replace(tzinfo=None)
	return parsed


def _table_multiselect(df, value) -> list[dict]:
	if not isinstance(value, list):
		raise TypeError("expected a list")
	link = next(field.fieldname for field in frappe.get_meta(df.options).fields if field.fieldtype == "Link")
	return [{link: item} for item in value]


def _text(df, value):
	if isinstance(value, list):
		return ", ".join(str(item) for item in value)
	if isinstance(value, dict):
		return json.dumps(value)
	return value


def _select(df, value):
	value = str(_text(df, value))
	options = [option for option in (df.options or "").split("\n") if option]
	if options and value not in options:
		raise ValueError(f"expected one of {', '.join(options)}")
	return value


def _json(df, value):
	return json.dumps(value) if isinstance(value, dict | list) else value


ATTACH = SOURCE_FIELD_TYPES["media"]
CONVERTERS = {
	"Check": _check,
	"Int": _int,
	**dict.fromkeys(("Float", "Currency", "Percent"), _float),
	"Date": _date,
	"Datetime": _datetime,
	"Table MultiSelect": _table_multiselect,
	**dict.fromkeys(STRING, _text),
	"Select": _select,
	**dict.fromkeys(("JSON", "Code"), _json),
}
