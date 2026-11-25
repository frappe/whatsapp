# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
import secrets
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from requests import HTTPError

from whatsapp.whatsapp.api.messages import send_flow, send_template
from whatsapp.whatsapp.api.test_messages import WithoutHostAccessGuards
from whatsapp.whatsapp.api.utils import humanize_error_message
from whatsapp.whatsapp.doctype.wa_profile.wa_profile import get_or_create_profile
from whatsapp.whatsapp.doctype.wa_template.wa_template import get_sendable_templates
from whatsapp.whatsapp.flows.flow_json_fixtures import PREFILLED
from whatsapp.whatsapp.flows.meta_fixtures import FlowMetaCase
from whatsapp.whatsapp.flows.template_fixtures import flow_button, make_flow, template_doc

MESSAGE_CLIENT = "whatsapp.whatsapp.doctype.wa_message.wa_message.WhatsApp"
PROFILE_INPUTS = [
	{"key": "first_name", "source_field": "first_name"},
	{"key": "last_name", "source_field": "last_name"},
	{"key": "sessions", "source_field": "simultaneous_sessions"},
	{"key": "enabled", "source_field": "enabled"},
]
UPDATE_BIO = {"action": "Update Reference", "fields": [{"source": "comment", "target_field": "bio"}]}


class FlowSendCase(WithoutHostAccessGuards, FlowMetaCase):
	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("WA Settings", "default_account", self.account)
		self.client = MagicMock()
		self.client.send_message.return_value = {"messages": [{"id": "wamid.sent"}]}
		self.start_patch(MESSAGE_CLIENT, return_value=self.client)
		self.phone = f"+1{secrets.randbelow(10**10):010d}"
		self.user = frappe.get_doc(
			doctype="User",
			email=f"flow-{frappe.generate_hash(length=6)}@example.com",
			first_name="Asha",
			simultaneous_sessions=3,
			send_welcome_email=0,
		).insert()

	def make_flow(self, **fields) -> str:
		return make_flow(self.account, frappe.generate_hash(length=8), **fields).name

	def sent_payload(self) -> dict:
		self.client.send_message.assert_called_once()
		return self.client.send_message.call_args.args[0]

	def recipient_phone(self, message_name: str) -> str:
		return frappe.db.get_value(
			"WA Profile", frappe.db.get_value("WA Message", message_name, "to"), "phone_number"
		)


class IntegrationTestFlowTemplateSend(FlowSendCase):
	def test_a_flow_button_sends_its_token_and_the_inputs_resolved_from_the_reference(self):
		flow = self.make_flow(flow_json=PREFILLED)
		template = self._approved_template([flow_button(flow, flow_inputs=PROFILE_INPUTS)])

		name = self._send(template)

		token = frappe.db.get_value("WA Message", name, "flow_token")
		self.assertTrue(token)
		self.assertEqual(
			self._button_components(),
			[
				{
					"type": "button",
					"sub_type": "flow",
					"index": "0",
					"parameters": [
						{
							"type": "action",
							"action": {
								"flow_token": f"{token}:0:{flow}",
								"flow_action_data": {"first_name": "Asha", "sessions": 3, "enabled": True},
							},
						}
					],
				}
			],
		)

	def test_each_flow_button_gets_a_component_with_its_index_among_all_buttons(self):
		feedback, survey = self.make_flow(), self.make_flow()
		template = self._approved_template(
			[
				{"button_type": "Quick Reply", "button_text": "Not now"},
				flow_button(feedback),
				flow_button(survey, text="Take the survey"),
			]
		)

		name = self._send(template)

		token = frappe.db.get_value("WA Message", name, "flow_token")
		self.assertEqual(
			[(c["index"], c["parameters"][0]["action"]) for c in self._button_components()],
			[("1", {"flow_token": f"{token}:1:{feedback}"}), ("2", {"flow_token": f"{token}:2:{survey}"})],
		)

	def test_a_template_with_flow_inputs_needs_a_reference_document(self):
		flow = self.make_flow(flow_json=PREFILLED)
		template = self._approved_template([flow_button(flow, flow_inputs=PROFILE_INPUTS)])

		with self.assertRaisesRegex(frappe.ValidationError, "Flow inputs from User"):
			send_template(template, self.phone)

		self.client.send_message.assert_not_called()

	def test_a_message_from_another_doctype_than_the_templates_cannot_fill_flow_inputs(self):
		flow = self.make_flow(flow_json=PREFILLED)
		template = self._approved_template([flow_button(flow, flow_inputs=PROFILE_INPUTS)])
		todo = frappe.get_doc(doctype="ToDo", description="Call Asha").insert()
		message = frappe.get_doc(
			doctype="WA Message",
			direction="Outgoing",
			to=get_or_create_profile(self.phone, self.account),
			whatsapp_account=self.account,
			is_template=1,
			whatsapp_template=template,
			reference_doctype="ToDo",
			reference_docname=todo.name,
		)

		with self.assertRaisesRegex(
			frappe.ValidationError, "fills Flow inputs from User; cannot send from ToDo"
		):
			message.insert()

		self.client.send_message.assert_not_called()

	def test_a_blocked_or_deprecated_flow_fails_the_send_before_meta_is_called(self):
		for status in ("Blocked", "Deprecated"):
			with self.subTest(status=status):
				flow = self.make_flow()
				template = self._approved_template([flow_button(flow)])
				frappe.db.set_value("WA Flow", flow, "status", status)

				name = self._send(template)

				message = frappe.db.get_value("WA Message", name, ["status", "error_message"], as_dict=True)
				self.assertEqual(message.status, "Failed")
				self.assertIn(f"is {status}", message.error_message)
				self.client.send_message.assert_not_called()

	def test_a_throttled_flow_refused_by_meta_is_recorded_with_readable_text(self):
		template = self._approved_template([flow_button(self.make_flow())])
		frappe.db.set_value(
			"WA Flow",
			frappe.db.get_value("WA Template Button", {"parent": template}, "flow"),
			"status",
			"Throttled",
		)
		self.client.send_message.side_effect = HTTPError(
			'{"error":{"code":132069,"message":"(#132069) Flow is throttled"}}'
		)

		name = self._send(template)

		self.client.send_message.assert_called_once()
		error = frappe.db.get_value("WA Message", name, "error_message")
		self.assertIn("10 messages an hour", humanize_error_message(error))

	def test_sendable_templates_carry_each_flow_buttons_icon(self):
		template = self._approved_template([flow_button(self.make_flow(), flow_icon="Review")])

		button = next(t for t in get_sendable_templates("User") if t.name == template)["buttons"][0]

		self.assertEqual(button["flow_icon"], "Review")
		self.assertNotIn("flow_inputs", button)

	def test_update_reference_needs_write_permission_on_the_reference(self):
		template = self._approved_template(
			[flow_button(self.make_flow(), flow_response_actions=[UPDATE_BIO])]
		)
		reader, writer = self._shared_user(write=0), self._shared_user(write=1)
		self.addCleanup(frappe.set_user, "Administrator")

		frappe.set_user(reader)
		with self.assertRaisesRegex(frappe.PermissionError, "write"):
			self._send(template)
		self.client.send_message.assert_not_called()

		frappe.set_user(writer)
		self._send(template)
		self.client.send_message.assert_called_once()

	def test_update_reference_needs_a_reference_of_the_templates_doctype(self):
		template = self._approved_template(
			[flow_button(self.make_flow(), flow_response_actions=[UPDATE_BIO])]
		)
		todo = frappe.get_doc(doctype="ToDo", description="Call Asha").insert()

		with self.assertRaisesRegex(frappe.ValidationError, "updates User"):
			send_template(template, self.phone, reference_doctype="ToDo", reference_docname=todo.name)
		with self.assertRaisesRegex(frappe.ValidationError, "updates User"):
			send_template(template, self.phone)

		self.client.send_message.assert_not_called()

	def _shared_user(self, write: int) -> str:
		return _desk_user_sharing(("User", self.user.name, write))

	def _approved_template(self, buttons: list[dict]) -> str:
		template = template_doc(self.account, buttons, reference_doctype="User").insert()
		frappe.db.set_value("WA Template", template.name, "status", "Approved")
		return template.name

	def _send(self, template: str) -> str:
		return send_template(template, self.phone, reference_doctype="User", reference_docname=self.user.name)

	def _button_components(self) -> list[dict]:
		return [c for c in self.sent_payload()["template"]["components"] if c["type"] == "button"]


class IntegrationTestSendFlow(FlowSendCase):
	def test_an_interactive_flow_message_carries_every_part(self):
		flow = self.make_flow()

		name = send_flow(
			flow,
			self.phone,
			"How did the deal go?",
			cta="Rate us",
			screen="WELCOME",
			data=json.dumps({"customer_name": "Asha"}),
			reference_doctype="User",
			reference_docname=self.user.name,
		)

		message = frappe.get_doc("WA Message", name)
		self.assertEqual(
			(message.flow, message.flow_mode, message.reference_docname), (flow, "Published", self.user.name)
		)
		self.assertEqual(
			self.sent_payload(),
			{
				"messaging_product": "whatsapp",
				"recipient_type": "individual",
				"to": self.recipient_phone(name),
				"type": "interactive",
				"interactive": {
					"type": "flow",
					"body": {"text": "How did the deal go?"},
					"action": {
						"name": "flow",
						"parameters": {
							"flow_message_version": "3",
							"flow_token": message.flow_token,
							"flow_id": flow,
							"flow_cta": "Rate us",
							"flow_action": "navigate",
							"flow_action_payload": {
								"screen": "WELCOME",
								"data": json.dumps({"customer_name": "Asha"}),
							},
						},
					},
				},
			},
		)

	def test_the_defaults_open_the_first_entry_screen_with_nothing_optional(self):
		send_flow(self.make_flow(), self.phone, "How did the deal go?")

		interactive = self.sent_payload()["interactive"]
		parameters = interactive["action"]["parameters"]
		self.assertEqual(set(interactive), {"type", "body", "action"})
		self.assertEqual(parameters["flow_cta"], "Open")
		self.assertEqual(parameters["flow_action_payload"], {"screen": "WELCOME"})
		self.assertNotIn("mode", parameters)

	def test_a_draft_flow_is_sent_only_in_draft_mode(self):
		draft = self.make_flow(status="Draft")

		with self.assertRaisesRegex(frappe.ValidationError, "Draft"):
			send_flow(draft, self.phone, "Try this form")
		self.client.send_message.assert_not_called()

		name = send_flow(draft, self.phone, "Try this form", mode="draft")
		self.assertEqual(self.sent_payload()["interactive"]["action"]["parameters"]["mode"], "draft")
		self.assertEqual(frappe.db.get_value("WA Message", name, "flow_mode"), "Draft")

	def test_sending_a_flow_needs_read_on_it_and_a_draft_needs_write(self):
		published, draft = self.make_flow(), self.make_flow(status="Draft")
		sender = _desk_user_sharing(("User", self.user.name, 0))

		def send(flow: str, **kwargs) -> str:
			return send_flow(
				flow,
				self.phone,
				"Try this form",
				reference_doctype="User",
				reference_docname=self.user.name,
				**kwargs,
			)

		self.addCleanup(frappe.set_user, "Administrator")

		frappe.set_user(sender)
		with self.assertRaises(frappe.PermissionError):
			send(published)

		frappe.set_user("Administrator")
		for flow in (published, draft):
			frappe.share.add_docshare(
				"WA Flow", flow, sender, read=1, flags={"ignore_share_permission": True}
			)
		frappe.set_user(sender)
		send(published)
		with self.assertRaises(frappe.PermissionError):
			send(draft, mode="draft")
		self.client.send_message.assert_called_once()

	def test_a_screen_that_is_not_an_entry_screen_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "RATE is not an entry screen"):
			send_flow(self.make_flow(), self.phone, "How did the deal go?", screen="RATE")
		self.client.send_message.assert_not_called()


def _desk_user_sharing(*shares: tuple[str, str, int]) -> str:
	"""A Desk User with read on each (doctype, name, write) document, and write where `write` is 1."""
	user = frappe.get_doc(
		doctype="User",
		email=f"flow-sender-{frappe.generate_hash(length=6)}@example.com",
		first_name="Sender",
		send_welcome_email=0,
		roles=[{"role": "Desk User"}],
	).insert(ignore_permissions=True)
	for doctype, name, write in shares:
		frappe.share.add_docshare(
			doctype, name, user.name, read=1, write=write, flags={"ignore_share_permission": True}
		)
	return user.name
