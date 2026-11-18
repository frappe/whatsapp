# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

# Flow JSON shaped after Meta's Flow JSON reference (version 7.x). Replace with real Flows when available.


def navigate(screen: str, payload: dict | None = None) -> dict:
	return {"name": "navigate", "next": {"type": "screen", "name": screen}, "payload": payload or {}}


def complete(payload: dict) -> dict:
	return {"name": "complete", "payload": payload}


def footer(label: str, action: dict) -> dict:
	return {"type": "Footer", "label": label, "on-click-action": action}


def screen(screen_id: str, children: list, **properties) -> dict:
	return {
		"id": screen_id,
		"title": screen_id.title(),
		**properties,
		"layout": {"type": "SingleColumnLayout", "children": children},
	}


OPTIONS = [{"id": "1", "title": "One"}, {"id": "2", "title": "Two"}]

DEAL_FEEDBACK = {
	"version": "7.1",
	"screens": [
		screen(
			"WELCOME",
			[
				{"type": "TextHeading", "text": "Hi ${data.customer_name}"},
				{"type": "TextBody", "text": "Tell us about ${data.product}"},
				footer("Start", navigate("RATE", {"customer_name": "${data.customer_name}"})),
			],
			data={
				"customer_name": {"type": "string", "__example__": "Asha"},
				"product": {"type": "string", "__example__": "CRM Pro"},
			},
		),
		screen(
			"RATE",
			[
				{
					"type": "Form",
					"name": "rate_form",
					"children": [
						{
							"type": "RadioButtonsGroup",
							"name": "rating",
							"label": "Rate us",
							"data-source": OPTIONS,
							"required": True,
						},
						{"type": "TextArea", "name": "comment", "label": "Comments"},
						footer(
							"Next",
							navigate("DONE", {"rating": "${form.rating}", "comment": "${form.comment}"}),
						),
					],
				}
			],
			data={"customer_name": {"type": "string", "__example__": "Asha"}},
		),
		screen(
			"DONE",
			[
				{"type": "TextBody", "text": "Thanks!"},
				footer("Send", complete({"rating": "${data.rating}", "comment": "${data.comment}"})),
			],
			terminal=True,
			success=True,
			data={
				"rating": {"type": "string", "__example__": "1"},
				"comment": {"type": "string", "__example__": "Great"},
			},
		),
	],
}

LEAD_QUALIFICATION = {
	"version": "7.1",
	"screens": [
		screen(
			"QUALIFY",
			[
				{
					"type": "RadioButtonsGroup",
					"name": "interest",
					"label": "Are you interested?",
					"data-source": [{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
				},
				{
					"type": "If",
					"condition": "${form.interest} == 'yes'",
					"then": [footer("Continue", navigate("INTERESTED"))],
					"else": [footer("Continue", navigate("NOT_INTERESTED"))],
				},
			],
			data={"lead_name": {"type": "string", "__example__": "Asha"}},
		),
		screen(
			"INTERESTED",
			[
				{
					"type": "Form",
					"name": "details",
					"children": [
						{"type": "TextInput", "name": "email", "label": "Email", "input-type": "email"},
						{"type": "TextInput", "name": "company", "label": "Company"},
						{"type": "TextInput", "name": "budget", "label": "Budget", "input-type": "number"},
						{
							"type": "TextInput",
							"name": "passcode",
							"label": "Passcode",
							"input-type": "password",
						},
						footer(
							"Submit",
							complete(
								{
									"outcome": "interested",
									"email": "${form.email}",
									"company": "${form.company}",
									"budget": "${form.budget}",
									"passcode": "${form.passcode}",
									"flow_token": "${data.flow_token}",
								}
							),
						),
					],
				}
			],
			terminal=True,
			sensitive=["budget"],
		),
		screen(
			"NOT_INTERESTED",
			[
				{"type": "Dropdown", "name": "reason", "label": "Why not?", "data-source": OPTIONS},
				footer(
					"Submit",
					complete(
						{
							"outcome": "not_interested",
							"reason": "${form.reason}",
							"summary": "`'Not interested: ' ${form.reason}`",
						}
					),
				),
			],
			terminal=True,
		),
	],
}

CUSTOMER_PROFILE = {
	"version": "7.1",
	"screens": [
		screen(
			"CONTACT",
			[
				{"type": "TextInput", "name": "full_name", "label": "Full name"},
				{"type": "TextInput", "name": "city", "label": "City"},
				{"type": "TextInput", "name": "zip", "label": "ZIP", "input-type": "number"},
				{"type": "CheckboxGroup", "name": "interests", "label": "Interests", "data-source": OPTIONS},
				footer("Next", navigate("CONSENT", {"full_name": "${form.full_name}"})),
			],
		),
		screen(
			"CONSENT",
			[
				{"type": "PhotoPicker", "name": "photo", "label": "Your photo"},
				{"type": "OptIn", "name": "agree", "label": "I agree to the terms"},
				{
					"type": "EmbeddedLink",
					"text": "Skip for now",
					"on-click-action": complete({"skipped": True}),
				},
				footer(
					"Done",
					complete(
						{
							"name": "${screen.CONSENT.data.full_name}",
							"address": {
								"city": "${screen.CONTACT.form.city}",
								"zip": "${screen.CONTACT.form.zip}",
							},
							"interests": "${screen.CONTACT.form.interests}",
							"agree": "${form.agree}",
							"photo": "${form.photo}",
						}
					),
				),
			],
			terminal=True,
			data={"full_name": {"type": "string", "__example__": "Asha"}},
		),
	],
}

CYCLIC = {
	"version": "7.1",
	"screens": [
		screen("A", [footer("Next", navigate("B", {"x": "${data.x}"}))], data={"x": {"type": "string"}}),
		screen(
			"B",
			[
				{
					"type": "NavigationList",
					"name": "choices",
					"list-items": [
						{
							"id": "back",
							"main-content": {"title": "Back"},
							"on-click-action": navigate("A", {"x": "${data.x}"}),
						},
						{
							"id": "finish",
							"main-content": {"title": "Finish"},
							"on-click-action": complete({"x": "${data.x}"}),
						},
					],
				}
			],
			terminal=True,
			data={"x": {"type": "string"}},
		),
	],
}

ROUTED = {
	"version": "7.1",
	"data_api_version": "3.0",
	"routing_model": {"START": ["NEXT"], "NEXT": []},
	"screens": [
		screen(
			"START",
			[footer("Go", {"name": "data_exchange", "payload": {}})],
			data={"profile": {"type": "object"}, "count": {"type": "number"}},
		),
		screen("NEXT", [footer("Done", complete({"ok": True}))], terminal=True),
	],
}

PREFILLED = {
	"version": "7.1",
	"screens": [
		screen(
			"PROFILE",
			[
				{"type": "TextHeading", "text": "Hi ${data.first_name} ${data.last_name}"},
				footer("Confirm", complete({"confirmed": True})),
			],
			terminal=True,
			data={
				"first_name": {"type": "string", "__example__": "Asha"},
				"last_name": {"type": "string", "__example__": "Rao"},
				"sessions": {"type": "number", "__example__": 1},
				"enabled": {"type": "boolean", "__example__": True},
			},
		),
	],
}
