import re
from typing import TypedDict, cast


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
	header_type: str
	header_text: str
	message: str
	footer: str
	buttons: list[ButtonRow]
	template_variables: list[TemplateVariableRow]


def get_template_variables(text: str) -> list[str]:
	if not text:
		return []
	return re.findall(r"\x7b\x7b\s*([^}]+)\s*\x7d\x7d", text)


# use find instead
def _find_example(variables, var_name: str) -> str:
	for v in variables:
		if v["variable_name"] == var_name:
			return v["variable_example"]
	return var_name


def build_create_template_payload(doc) -> CreateTemplatePayload:
	components = []

	if doc.header_type:
		header = {"type": "HEADER", "format": doc.header_type}
		if doc.header_type == "TEXT" and doc.header_text:
			header["text"] = doc.header_text
			header_vars = get_template_variables(doc.header_text)
			if header_vars:
				header["example"] = {
					"header_text_named_params": [
						{"param_name": v, "example": _find_example(doc.template_variables, v)}
						for v in header_vars
					]
				}
		components.append(header)

	body = {"type": "BODY", "text": doc.message}
	body_vars = get_template_variables(doc.message)
	if body_vars:
		body["example"] = {
			"body_text_named_params": [
				{"param_name": v, "example": _find_example(doc.template_variables, v)}
				for v in body_vars
			]
		}
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

	return {
		"name": doc.template_name,
		"language": doc.language,
		"category": doc.template_type,
		"components": components,
	}


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
	doc = {
		"template_name": data.get("name"),
		"template_type": data.get("category"),
		"language": data.get("language"),
	}

	header_type = ""
	header_text = ""
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

		elif comp_type == "BODY":
			message = comp.get("text", "")
			variable_rows.extend(_resolve_examples(message, comp))

		elif comp_type == "FOOTER":
			footer = comp.get("text", "")

		elif comp_type == "BUTTONS":
			for btn in comp.get("buttons", []):
				buttons.append(
					{
						"button_type": btn.get("type"),
						"button_text": btn.get("text"),
						"url": btn.get("url", ""),
						"phone_number": btn.get("phone_number", ""),
					}
				)

	doc["header_type"] = header_type
	doc["header_text"] = header_text
	doc["message"] = message
	doc["footer"] = footer
	doc["buttons"] = buttons

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
