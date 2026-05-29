import re
from typing import TypedDict, cast

import frappe


class TemplateVariableRow(TypedDict):
	variable_name: str
	variable_example: str
	variable_field: str


class ButtonRow(TypedDict):
	button_type: str
	button_text: str
	url: str
	phone_number: str


class NamedParam(TypedDict):
	param_name: str
	example: str


class CreateTemplatePayload(TypedDict):
	name: str
	language: str
	category: str
	components: list[dict]


class TemplateMessagePayload(TypedDict):
	messaging_product: str
	recipient_type: str
	to: str
	type: str
	template: dict


class ParsedTemplateDoc(TypedDict):
	template_name: str
	template_type: str
	language: str
	status: str
	header_type: str
	header_text: str
	header_media_handle: str
	message: str
	footer: str
	buttons: list[ButtonRow]
	template_variables: list[TemplateVariableRow]
	variable_format: str


def get_template_variables(text: str) -> list[str]:
	if not text:
		return []
	return re.findall(r"\x7b\x7b\s*([^}]+)\s*\x7d\x7d", text)


def _find_example(variables, var_name: str) -> str:
	for v in variables:
		if isinstance(v, dict):
			if v["variable_name"] == var_name:
				return v["variable_example"]
		else:
			if v.variable_name == var_name:
				return v.variable_example
	return var_name


def _build_example(variable_format: str, variables, var_names: list[str]) -> dict:
	is_positional = variable_format == "positional"
	if is_positional:
		return {"body_text": [[_find_example(variables, v) for v in var_names]]}
	return {
		"body_text_named_params": [
			{"param_name": v, "example": _find_example(variables, v)} for v in var_names
		]
	}


def _build_header_example(variable_format: str, variables, var_names: list[str]) -> dict:
	is_positional = variable_format == "positional"
	if is_positional:
		return {"header_text": [_find_example(variables, v) for v in var_names]}
	return {
		"header_text_named_params": [
			{"param_name": v, "example": _find_example(variables, v)} for v in var_names
		]
	}


def build_create_template_payload(doc) -> CreateTemplatePayload:
	variable_format = getattr(doc, "variable_format", None) or "named"
	components = []

	if doc.header_type:
		header = {"type": "HEADER", "format": doc.header_type}
		if doc.header_type == "TEXT" and doc.header_text:
			header["text"] = doc.header_text
			header_vars = get_template_variables(doc.header_text)
			if header_vars:
				header["example"] = _build_header_example(
					variable_format, doc.template_variables, header_vars
				)
		elif doc.header_type in ("IMAGE", "DOCUMENT", "VIDEO", "GIF") and doc.header_media_handle:
			header["example"] = {"header_handle": [doc.header_media_handle]}
		components.append(header)

	body = {"type": "BODY", "text": doc.message}
	body_vars = get_template_variables(doc.message)
	if body_vars:
		body["example"] = _build_example(variable_format, doc.template_variables, body_vars)
	components.append(body)

	if doc.footer:
		components.append({"type": "FOOTER", "text": doc.footer})

	if doc.buttons:
		buttons_payload = []
		for btn in doc.buttons:
			if btn.button_type == "COPY_CODE":
				continue
			b = {"type": btn.button_type, "text": btn.button_text}
			if btn.button_type == "URL":
				b["url"] = btn.url
			elif btn.button_type == "PHONE_NUMBER":
				b["phone_number"] = btn.phone_number
			buttons_payload.append(b)
		if buttons_payload:
			components.append({"type": "BUTTONS", "buttons": buttons_payload})

	payload = {
		"name": doc.template_name,
		"language": doc.language,
		"category": doc.template_type,
		"components": components,
	}

	if variable_format == "named":
		payload["parameter_format"] = "named"

	return payload


def _resolve_examples(text: str, comp: dict) -> list[tuple[str, str]]:
	vars = get_template_variables(text)
	if not vars:
		return []

	example = comp.get("example", {}) or {}
	is_positional = all(v.isdigit() for v in vars)
	comp_type = comp.get("type", "").upper()

	if is_positional:
		if comp_type == "HEADER":
			examples_list = example.get("header_text", [])
		else:
			examples_list = example.get("body_text", [[]])[0] if example.get("body_text") else []
		return [(v, examples_list[i] if i < len(examples_list) else v) for i, v in enumerate(vars)]

	if comp_type == "HEADER":
		named = example.get("header_text_named_params", [])
	else:
		named = example.get("body_text_named_params", [])
	lookup = {np["param_name"]: np["example"] for np in named}
	return [(v, lookup.get(v, v)) for v in vars]


def parse_whatsapp_template_to_doc(data: dict) -> ParsedTemplateDoc:
	api_status = data.get("status", "")
	status_map = {
		"APPROVED": "APPROVED",
		"REJECTED": "REJECTED",
		"PENDING": "PENDING",
	}
	doc = {
		"template_name": data.get("name"),
		"template_type": data.get("category"),
		"language": data.get("language"),
		"status": status_map.get(api_status, "PENDING"),
	}

	header_type = ""
	header_text = ""
	header_media_handle = ""
	message = ""
	footer = ""
	buttons = []
	variable_rows = []

	for comp in data.get("components", []):
		comp_type = comp.get("type", "").upper()

		if comp_type == "HEADER":
			header_type = comp.get("format", "")
			if header_type.upper() == "TEXT":
				header_text = comp.get("text", "")
				variable_rows.extend(_resolve_examples(header_text, comp))
			elif header_type.upper() in ("IMAGE", "DOCUMENT", "VIDEO", "GIF"):
				example = comp.get("example", {}) or {}
				handles = example.get("header_handle", [])
				if handles:
					header_media_handle = handles[0]

		elif comp_type == "BODY":
			message = comp.get("text", "")
			variable_rows.extend(_resolve_examples(message, comp))

		elif comp_type == "FOOTER":
			footer = comp.get("text", "")

		elif comp_type == "BUTTONS":
			for btn in comp.get("buttons", []):
				btn_url = btn.get("url", "")
				buttons.append(
					{
						"button_type": btn.get("type"),
						"button_text": btn.get("text"),
						"url": btn_url,
						"phone_number": btn.get("phone_number", ""),
					}
				)
				if btn.get("type") == "URL" and btn_url:
					url_vars = get_template_variables(btn_url)
					for var in url_vars:
						variable_rows.append((var, ""))

	doc["header_type"] = header_type
	doc["header_text"] = header_text
	doc["header_media_handle"] = header_media_handle
	doc["message"] = message
	doc["footer"] = footer
	doc["buttons"] = buttons

	variable_format = "named"
	if variable_rows:
		all_digit = all(v[0].isdigit() for v in variable_rows)
		if all_digit:
			variable_format = "positional"
	doc["variable_format"] = variable_format

	seen = set()
	unique_vars = []
	for name, example in variable_rows:
		if name not in seen:
			seen.add(name)
			unique_vars.append((name, example))

	doc["template_variables"] = [
		{"variable_name": name, "variable_example": example, "variable_field": ""}
		for name, example in unique_vars
	]

	return cast(ParsedTemplateDoc, doc)


def build_template_message_payload(
	to: str,
	template_doc,
	body_parameters: dict[str, str] | None = None,
	header_parameters: str | dict | None = None,
) -> TemplateMessagePayload:
	payload = {
		"messaging_product": "whatsapp",
		"recipient_type": "individual",
		"to": to,
		"type": "template",
		"template": {
			"name": template_doc.template_name,
			"language": {"code": template_doc.language},
		},
	}

	components = []

	if header_parameters is not None and template_doc.header_type:
		if isinstance(header_parameters, str):
			import json

			header_parameters = json.loads(header_parameters)

		if template_doc.header_type == "TEXT":
			header_vars = get_template_variables(template_doc.header_text)
			param_name = header_vars[0] if header_vars else "1"
			components.append(
				{
					"type": "header",
					"parameters": [
						{
							"type": "text",
							"parameter_name": param_name,
							"text": str(header_parameters),
						}
					],
				}
			)
		else:
			media_type = template_doc.header_type.lower()
			params = {"id": header_parameters["id"]} if isinstance(header_parameters, dict) else {}
			if (
				media_type == "document"
				and isinstance(header_parameters, dict)
				and "filename" in header_parameters
			):
				params["filename"] = header_parameters["filename"]
			components.append(
				{
					"type": "header",
					"parameters": [{"type": media_type, media_type: params}],
				}
			)

	if body_parameters:
		components.append(
			{
				"type": "body",
				"parameters": [
					{"type": "text", "parameter_name": name, "text": value}
					for name, value in body_parameters.items()
				],
			}
		)

	if components:
		payload["template"]["components"] = components

	return cast(TemplateMessagePayload, payload)


def build_text_message_payload(
	to: str,
	text: str,
	preview_url: bool = False,
) -> dict:
	return {
		"messaging_product": "whatsapp",
		"recipient_type": "individual",
		"to": to,
		"type": "text",
		"text": {"preview_url": preview_url, "body": text},
	}


def build_reaction_message_payload(
	to: str,
	message_id: str,
	emoji: str | None = None,
) -> dict:
	payload = {
		"messaging_product": "whatsapp",
		"recipient_type": "individual",
		"to": to,
		"type": "reaction",
		"reaction": {"message_id": message_id},
	}
	if emoji:
		payload["reaction"]["emoji"] = emoji
	return payload


def build_interactive_buttons_payload(
	to: str,
	body_text: str,
	buttons: list[dict],
	footer: str | None = None,
) -> dict:
	payload = {
		"messaging_product": "whatsapp",
		"recipient_type": "individual",
		"to": to,
		"type": "interactive",
		"interactive": {
			"type": "button",
			"body": {"text": body_text},
			"action": {
				"buttons": [
					{"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
					for b in buttons
				]
			},
		},
	}
	if footer:
		payload["interactive"]["footer"] = {"text": footer}
	return payload


def build_interactive_list_payload(
	to: str,
	body_text: str,
	items: list[dict],
	button_text: str = "Options",
	footer: str | None = None,
	header_text: str | None = None,
) -> dict:
	payload = {
		"messaging_product": "whatsapp",
		"recipient_type": "individual",
		"to": to,
		"type": "interactive",
		"interactive": {
			"type": "list",
			"body": {"text": body_text},
			"action": {
				"button": button_text,
				"sections": [
					{
						"title": "Options",
						"rows": [
							{
								"id": i["id"],
								"title": i["title"],
								"description": i.get("description", ""),
							}
							for i in items
						],
					}
				],
			},
		},
	}
	if footer:
		payload["interactive"]["footer"] = {"text": footer}
	if header_text:
		payload["interactive"]["header"] = {"type": "text", "text": header_text}
	return payload


def build_media_message_payload(
	to: str,
	media_id: str,
	mime_type: str,
	caption: str | None = None,
	file_name: str | None = None,
) -> dict:
	if mime_type.startswith("image/"):
		media_type = "image"
	elif mime_type.startswith("video/"):
		media_type = "video"
	elif mime_type.startswith("audio/"):
		media_type = "audio"
	else:
		media_type = "document"

	payload = {
		"messaging_product": "whatsapp",
		"recipient_type": "individual",
		"to": to,
		"type": media_type,
	}

	media_obj = {"id": media_id}
	if caption:
		media_obj["caption"] = caption
	if media_type == "document" and file_name:
		media_obj["filename"] = file_name

	payload[media_type] = media_obj
	return payload


@frappe.whitelist()
def get_logs(
	event_type: str | None = None,
	level: str | None = None,
	account: str | None = None,
	limit: int = 100,
) -> list[dict]:
	filters = {}
	if event_type:
		filters["event_type"] = event_type
	if level:
		filters["level"] = level
	if account:
		filters["account"] = account
	return frappe.get_all(
		"WhatsApp Log",
		filters=filters or None,
		fields=["name", "level", "event_type", "message", "account", "timestamp", "reference_doctype", "reference_docname"],
		order_by="creation desc",
		limit=limit,
	)


def log(
	level: str,
	event_type: str,
	message: str,
	*,
	account: str | None = None,
	reference_doctype: str | None = None,
	reference_docname: str | None = None,
	request_data: str | dict | None = None,
	response_data: str | dict | None = None,
	traceback: str | None = None,
) -> str | None:
	try:
		if isinstance(request_data, dict):
			request_data = frappe.as_json(request_data)
		if isinstance(response_data, dict):
			response_data = frappe.as_json(response_data)
		doc = frappe.get_doc(
			{
				"doctype": "WhatsApp Log",
				"level": level,
				"event_type": event_type,
				"message": message,
				"account": account,
				"reference_doctype": reference_doctype,
				"reference_docname": reference_docname,
				"request_data": request_data,
				"response_data": response_data,
				"traceback": traceback or frappe.get_traceback() if level == "Error" else None,
				"timestamp": frappe.utils.now_datetime(),
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()
		return doc.name
	except Exception:
		frappe.logger("whatsapp").error("Failed to create WhatsApp Log entry", exc_info=True)
		return None
