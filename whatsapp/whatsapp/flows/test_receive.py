# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
import secrets
from unittest.mock import MagicMock, patch

import frappe

from whatsapp.whatsapp.api.messages import get_messages, send_flow, send_template
from whatsapp.whatsapp.doctype.wa_message.wa_message import WAMessage
from whatsapp.whatsapp.flows.flow_json_fixtures import LEAD_QUALIFICATION
from whatsapp.whatsapp.flows.meta_fixtures import messages_payload, nfm_reply
from whatsapp.whatsapp.flows.template_fixtures import flow_button, template_doc
from whatsapp.whatsapp.flows.test_send import FlowSendCase
from whatsapp.whatsapp.webhook import handler

RATING = {"rating": "5", "comment": "Great"}
LEAD_ANSWERS = {
	"outcome": "interested",
	"company": "Acme",
	"email": "asha@example.com",
	"budget": 5000,
	"passcode": "1234",
	"tags": ["vip", "early"],
}


class FlowResponseCase(FlowSendCase):
	"""Sends Flows from a User through the mocked Graph client, and delivers responses through the webhook."""

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("WA Settings", "webhook_secret", "")
		self.client.send_message.side_effect = lambda payload: {
			"messages": [{"id": f"wamid.{secrets.token_hex(8)}"}]
		}

	def send_template(self, buttons: list[dict]) -> frappe._dict:
		template = template_doc(self.account, buttons, reference_doctype="User").insert()
		frappe.db.set_value("WA Template", template.name, "status", "Approved")
		name = send_template(
			template.name, self.phone, reference_doctype="User", reference_docname=self.user.name
		)
		return self.sent(name)

	def send_flow(self, flow_json: dict | None = None) -> frappe._dict:
		flow = self.make_flow(**({"flow_json": flow_json} if flow_json else {}))
		name = send_flow(
			flow, self.phone, "Tell us more", reference_doctype="User", reference_docname=self.user.name
		)
		return self.sent(name)

	def sent(self, name: str) -> frappe._dict:
		return frappe.db.get_value(
			"WA Message", name, ["name", "flow", "flow_token", "message_id"], as_dict=True
		)

	def respond(
		self, answers: dict | str, token: str | None = None, context_id: str | None = None, sender=None
	):
		if token and isinstance(answers, dict):
			answers = {"flow_token": token, **answers}
		message = nfm_reply((sender or self.phone).lstrip("+"), answers, context_id)
		self.deliver(message)
		return frappe.get_doc("WA Message", {"message_id": message["id"]})

	def deliver(self, message: dict) -> None:
		frappe.local.form_dict = frappe._dict(
			messages_payload(frappe.db.get_value("WA Account", self.account, "phone_id"), message)
		)
		frappe.local.request = MagicMock(method="POST")
		self.addCleanup(
			lambda: delattr(frappe.local, "request") if hasattr(frappe.local, "request") else None
		)
		handler()

	def answers_of(self, response, reference: list[str]) -> list[dict]:
		rows = get_messages(json.dumps([reference]))
		return next(row for row in rows if row["name"] == response.name)["flow_answers"]

	def flow_logs(self, level: str) -> list[str]:
		return frappe.get_all("WA Log", filters={"event_type": "Flow", "level": level}, pluck="message")


class IntegrationTestFlowResponseMatching(FlowResponseCase):
	def test_a_token_matches_the_template_send_and_names_the_button_that_opened_the_flow(self):
		feedback, survey = self.make_flow(), self.make_flow()
		send = self.send_template(
			[
				{"button_type": "Quick Reply", "button_text": "Not now"},
				flow_button(feedback),
				flow_button(survey, text="Take the survey"),
			]
		)

		response = self.respond(RATING, token=f"{send.flow_token}:2:{survey}")

		self.assertEqual(
			(
				response.reply_to_message,
				response.reference_doctype,
				response.reference_docname,
				response.flow_button_index,
				response.flow,
			),
			(send.name, "User", self.user.name, 2, survey),
		)
		self.assertTrue(response.flow_template)
		self.assertEqual(json.loads(response.flow_response), RATING)
		self.assertFalse(response.is_template)

	def test_a_token_names_the_buttons_flow_so_the_response_runs_its_actions(self):
		flow = self.make_flow()
		todo = {
			"action": "Create Document",
			"doctype": "ToDo",
			"fields": [{"source": "comment", "target_field": "description"}],
		}
		send = self.send_template([flow_button(flow, flow_response_actions=[todo])])

		response = self.respond(RATING, token=f"{send.flow_token}:0:{flow}")

		self.assertEqual((response.flow_button_index, response.flow), (0, flow))
		self.assertTrue(response.flow_template)
		self.assertEqual(frappe.db.count("ToDo", {"description": ("like", "%Great%")}), 1)

	def test_a_button_moved_after_the_send_runs_no_actions_and_masks_with_the_sent_flow(self):
		qualify, feedback = self.make_flow(flow_json=LEAD_QUALIFICATION), self.make_flow()
		todo = {
			"action": "Create Document",
			"doctype": "ToDo",
			"fields": [{"source": "company", "target_field": "description"}],
		}
		send = self.send_template(
			[
				flow_button(qualify, text="Qualify", flow_response_actions=[todo]),
				flow_button(feedback, flow_response_actions=[todo]),
			]
		)
		template = frappe.db.get_value("WA Message", send.name, "whatsapp_template")
		for idx, flow in ((1, feedback), (2, qualify)):
			frappe.db.set_value("WA Template Button", {"parent": template, "idx": idx}, "flow", flow)
		frappe.clear_document_cache("WA Template", template)

		response = self.respond(LEAD_ANSWERS, token=f"{send.flow_token}:0:{qualify}")

		self.assertEqual((response.flow, response.flow_template), (qualify, None))
		self.assertEqual(frappe.db.count("ToDo", {"description": ("like", "%Acme%")}), 0)
		self.assertNotIn("1234", response.message)
		self.assertNotIn("5000", response.message)
		self.assertTrue(any("no longer" in message for message in self.flow_logs("Warning")))

	def test_a_response_without_a_token_is_matched_by_its_context(self):
		flow = self.make_flow()
		send = self.send_template([flow_button(flow)])

		response = self.respond(RATING, context_id=send.message_id)

		self.assertEqual(
			(
				response.reply_to_message,
				response.reference_docname,
				response.flow_button_index,
				response.flow,
			),
			(send.name, self.user.name, 0, flow),
		)

	def test_a_tokenless_response_to_several_flow_buttons_is_kept_without_its_flow(self):
		send = self.send_template(
			[flow_button(self.make_flow()), flow_button(self.make_flow(), text="Survey")]
		)

		response = self.respond(RATING, context_id=send.message_id)

		self.assertEqual(
			(response.reply_to_message, response.reference_docname, response.flow),
			(send.name, self.user.name, None),
		)
		self.assertTrue(response.flow_template)
		self.assertEqual(json.loads(response.flow_response), RATING)
		self.assertTrue(any("several Flow buttons" in message for message in self.flow_logs("Warning")))

	def test_an_interactive_send_gives_its_flow_to_the_response(self):
		send = self.send_flow()

		response = self.respond(RATING, token=send.flow_token)

		self.assertEqual(
			(response.reply_to_message, response.flow, response.flow_template),
			(send.name, send.flow, None),
		)

	def test_a_token_from_another_sender_does_not_match(self):
		send = self.send_flow()

		response = self.respond(RATING, token=send.flow_token, sender=f"+1{secrets.randbelow(10**10):010d}")

		self.assertEqual((response.reply_to_message, response.flow), (None, None))
		self.assertNotEqual(response.reference_doctype, "User")

	def test_an_unmatched_response_goes_through_append_actions_and_still_fires_its_event(self):
		account = frappe.get_doc("WA Account", self.account)
		account.append(
			"append_actions",
			{"trigger_on": "Incoming", "append_to": "ToDo", "message_field": "description"},
		)
		account.save()
		events = []
		with patch.object(
			WAMessage,
			"run_notifications",
			autospec=True,
			side_effect=lambda doc, method: events.append(method),
		):
			response = self.respond(RATING)

		self.assertEqual(response.reference_doctype, "ToDo")
		self.assertEqual(response.message, "Form submitted")
		self.assertEqual(
			frappe.db.get_value("ToDo", response.reference_docname, "description"), "Form submitted"
		)
		self.assertIn("on_flow_response", events)
		answers = self.answers_of(response, ["ToDo", response.reference_docname])
		self.assertEqual(
			answers,
			[
				{"key": "rating", "label": "rating", "value": "5", "masked": False},
				{"key": "comment", "label": "comment", "value": "Great", "masked": False},
			],
		)

	def test_flow_fields_are_set_before_the_message_is_submitted(self):
		send = self.send_flow()
		seen = {}

		def record(doc, method):
			if method == "before_submit" and doc.direction == "Incoming":
				seen.update(doc.as_dict())

		with patch.object(WAMessage, "run_notifications", autospec=True, side_effect=record):
			self.respond(RATING, token=send.flow_token)

		self.assertEqual(
			(
				seen["reply_to_message"],
				seen["flow"],
				seen["reference_docname"],
				json.loads(seen["flow_response"]),
			),
			(send.name, send.flow, self.user.name, RATING),
		)
		self.assertEqual(seen["message"], "Rate us: 5 · Comments: Great")

	def test_invalid_response_json_is_stored_empty_with_a_warning(self):
		send = self.send_flow()

		response = self.respond("{not json", context_id=send.message_id)

		self.assertEqual((json.loads(response.flow_response), response.message), ({}, "Sent"))
		self.assertEqual(response.reply_to_message, send.name)
		self.assertTrue(any("not valid JSON" in message for message in self.flow_logs("Warning")))


class IntegrationTestFlowResponseDisplay(FlowResponseCase):
	def test_the_message_body_summarises_the_answers_without_sensitive_ones(self):
		send = self.send_flow(LEAD_QUALIFICATION)

		response = self.respond(LEAD_ANSWERS, token=send.flow_token)

		self.assertEqual(
			response.message,
			"outcome: interested · Email: asha@example.com · Company: Acme · tags: vip, early",
		)

	def test_the_conversation_labels_answers_in_the_outlines_order_and_masks_sensitive_values(self):
		send = self.send_flow(LEAD_QUALIFICATION)
		response = self.respond(LEAD_ANSWERS, token=send.flow_token)

		rows = {row["name"]: row for row in get_messages(json.dumps([["User", self.user.name]]))}

		self.assertEqual(
			(rows[send.name]["flow_name"], rows[send.name]["flow_cta"]), (f"Flow {send.flow}", "Open")
		)
		self.assertEqual(
			rows[response.name]["flow_answers"],
			[
				{"key": "outcome", "label": "outcome", "value": "interested", "masked": False},
				{"key": "email", "label": "Email", "value": "asha@example.com", "masked": False},
				{"key": "company", "label": "Company", "value": "Acme", "masked": False},
				{"key": "budget", "label": "Budget", "value": None, "masked": True},
				{"key": "passcode", "label": "Passcode", "value": None, "masked": True},
				{"key": "tags", "label": "tags", "value": ["vip", "early"], "masked": False},
			],
		)
		self.assertNotIn("flow_response", rows[response.name])
		self.assertNotIn("1234", json.dumps(rows, default=str))

	def test_a_response_matched_only_by_its_token_quotes_the_send(self):
		send = self.send_flow()
		response = self.respond(RATING, token=send.flow_token)

		row = next(
			row
			for row in get_messages(json.dumps([["User", self.user.name]]))
			if row["name"] == response.name
		)

		self.assertEqual(
			(row["reply_to"], row["reply_to_direction"], row["reply_message"]),
			(send.name, "Outgoing", "Tell us more"),
		)

	def test_a_response_without_its_flow_masks_what_any_flow_button_of_the_template_marks_sensitive(self):
		send = self.send_template(
			[
				flow_button(self.make_flow()),
				flow_button(self.make_flow(flow_json=LEAD_QUALIFICATION), text="Qualify"),
			]
		)

		response = self.respond(LEAD_ANSWERS, context_id=send.message_id)

		self.assertIsNone(response.flow)
		self.assertNotIn("1234", response.message)
		self.assertNotIn("5000", response.message)
		masked = {
			row["key"]
			for row in self.answers_of(response, ["User", self.user.name])
			if row["masked"] and row["value"] is None
		}
		self.assertEqual(masked, {"budget", "passcode"})

	def test_raw_answers_are_hidden_from_users_without_system_manager(self):
		send = self.send_flow(LEAD_QUALIFICATION)
		response = self.respond(LEAD_ANSWERS, token=send.flow_token)
		reader = frappe.get_doc(
			doctype="User",
			email=f"flow-reader-{frappe.generate_hash(length=6)}@example.com",
			first_name="Reader",
			send_welcome_email=0,
			roles=[{"role": "Desk User"}],
		).insert(ignore_permissions=True)
		frappe.share.add_docshare(
			"WA Message", response.name, reader.name, flags={"ignore_share_permission": True}
		)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(reader.name)

		fetched = frappe.client.get("WA Message", response.name)

		self.assertEqual(fetched["name"], response.name)
		self.assertNotIn("1234", json.dumps(fetched, default=str))
