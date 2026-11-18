# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
from datetime import date, datetime
from unittest.mock import patch

import frappe
from frappe.utils import getdate

from whatsapp.whatsapp.doctype.wa_message.wa_message import WAMessage
from whatsapp.whatsapp.flows.flow_json_fixtures import CUSTOMER_PROFILE, DEAL_FEEDBACK
from whatsapp.whatsapp.flows.meta_fixtures import nfm_reply
from whatsapp.whatsapp.flows.template_fixtures import flow_button
from whatsapp.whatsapp.flows.test_receive import RATING, FlowResponseCase


def update_reference(*fields: tuple[str, str], condition: str | None = None) -> dict:
	return _action("Update Reference", fields, condition=condition)


def create_document(doctype: str, *fields: tuple[str, str]) -> dict:
	return _action("Create Document", fields, doctype=doctype)


def _action(kind: str, fields, **extra) -> dict:
	return {
		"action": kind,
		**{key: value for key, value in extra.items() if value},
		"fields": [{"source": source, "target_field": target} for source, target in fields],
	}


class IntegrationTestResponseActions(FlowResponseCase):
	def test_update_reference_writes_the_answers_and_skips_missing_keys(self):
		frappe.db.set_value("User", self.user.name, "last_name", "Rao")

		response = self.complete(
			[update_reference(("comment", "bio"), ("rating", "location"), ("missing_key", "last_name"))]
		)

		self.assertEqual(self.user_values("bio", "location", "last_name"), ("Great", "5", "Rao"))
		self.assertTrue(
			any(f"User {self.user.name}" in message for message in self.message_logs(response, "Info"))
		)

	def test_create_document_inserts_a_record_from_answers_and_message_details(self):
		response = self.complete(
			[
				create_document(
					"ToDo",
					("comment", "description"),
					("reference_doctype", "reference_type"),
					("reference_name", "reference_name"),
					("received_at", "date"),
				)
			]
		)

		todo = frappe.get_all(
			"ToDo",
			filters={"reference_type": "User", "reference_name": self.user.name},
			fields=["name", "description", "date"],
		)
		self.assertEqual(len(todo), 1)
		self.assertIn("Great", todo[0].description)
		self.assertEqual(todo[0].date, getdate(response.timestamp))
		self.assertTrue(
			any(f"ToDo {todo[0].name}" in message for message in self.message_logs(response, "Info"))
		)

	def test_a_condition_sees_the_response_the_reference_and_the_message(self):
		self.complete(
			[
				update_reference(
					("rating", "location"),
					condition="response.rating == '5' and doc.first_name == 'Asha' and message.direction == 'Incoming'",
				),
				update_reference(("comment", "bio"), condition="response.rating != '5'"),
			]
		)

		self.assertEqual(self.user_values("location", "bio"), ("5", None))

	def test_a_condition_cannot_write_through_the_documents_it_sees(self):
		response = self.complete(
			[
				update_reference(
					("rating", "location"),
					condition="doc.db_set('bio', 'written') or message.db_set('flow_response', '{}')",
				)
			]
		)

		self.assertEqual(self.user_values("location", "bio"), (None, None))
		self.assertEqual(
			json.loads(frappe.db.get_value("WA Message", response.name, "flow_response")), RATING
		)
		self.assertEqual(len(self.message_logs(response, "Error")), 1)

	def test_a_failing_action_is_logged_and_skipped_without_losing_the_message(self):
		response = self.complete(
			[create_document("Note", ("comment", "content")), update_reference(("rating", "location"))]
		)

		self.assertTrue(frappe.db.exists("WA Message", response.name))
		self.assertEqual(self.user_values("location"), ("5",))
		errors = frappe.get_all(
			"WA Log",
			filters={"reference_docname": response.name, "level": "Error"},
			fields=["message", "traceback"],
		)
		self.assertEqual(len(errors), 1)
		self.assertIn("Create Document", errors[0].message)
		self.assertTrue(errors[0].traceback)

	def test_a_delivery_that_arrives_while_the_first_holds_the_lock_runs_no_actions(self):
		flow = self.make_flow()
		send = self.send_template(
			[flow_button(flow, flow_response_actions=[create_document("ToDo", ("comment", "description"))])]
		)
		message = nfm_reply(self.phone.lstrip("+"), {"flow_token": f"{send.flow_token}:0", **RATING})
		first_delivery = []

		def first_delivery_commits_while_waiting(profile):
			if not first_delivery:
				first_delivery.append(profile)
				self.deliver(message)

		with patch(
			"whatsapp.whatsapp.webhook.lock_profile", side_effect=first_delivery_commits_while_waiting
		):
			self.deliver(message)

		self.assertEqual(frappe.db.count("WA Message", {"message_id": message["id"]}), 1)
		self.assertEqual(frappe.db.count("ToDo", {"description": ("like", "%Great%")}), 1)

	def test_notifications_and_server_scripts_after_submit_see_the_updated_reference(self):
		seen = []

		def record(event):
			return lambda doc, method, *args: (
				seen.append((event, method, self.user_values("location")[0]))
				if doc.doctype == "WA Message" and doc.direction == "Incoming"
				else None
			)

		with (
			patch("frappe.model.document.run_server_script_for_doc_event", side_effect=record("script")),
			patch.object(WAMessage, "run_notifications", autospec=True, side_effect=record("notification")),
		):
			self.complete([update_reference(("rating", "location"))])

		self.assertIn(("script", "on_submit", "5"), seen)
		self.assertIn(("notification", "on_submit", "5"), seen)
		self.assertIn(("notification", "on_flow_response", "5"), seen)

	def test_values_are_converted_to_the_target_field_type(self):
		role_profiles = [self.role_profile(), self.role_profile()]
		answers = {
			"name": f"_Test Flow Coin {frappe.generate_hash(length=6)}",
			"address": {"city": "Pune", "zip": "7"},
			"interests": role_profiles,
			"agree": True,
			"consented": "true",
			"birthday": "1990-05-17",
			"seen_at": "2026-11-17T10:30:00",
			"fraction": "0.25",
			"logins": "many",
			"photo": [{"media_id": "1234", "file_name": "me.jpg"}],
		}

		response = self.complete(
			[
				update_reference(
					("agree", "mute_sounds"),
					("consented", "send_me_a_copy"),
					("address.zip", "simultaneous_sessions"),
					("address.city", "location"),
					("address", "home_settings"),
					("interests", "role_profiles"),
					("interests", "bio"),
					("birthday", "birth_date"),
					("seen_at", "last_active"),
					("logins", "login_after"),
					("photo", "user_image"),
				),
				create_document(
					"Currency", ("name", "currency_name"), ("fraction", "smallest_currency_fraction_value")
				),
				create_document("Error Log", ("whole_response", "error")),
			],
			flow_json=CUSTOMER_PROFILE,
			answers=answers,
		)

		user = frappe.get_doc("User", self.user.name)
		self.assertEqual(
			(user.mute_sounds, user.send_me_a_copy, user.simultaneous_sessions, user.location),
			(1, 1, 7, "Pune"),
		)
		self.assertEqual(json.loads(user.home_settings), {"city": "Pune", "zip": "7"})
		self.assertEqual([row.role_profile for row in user.role_profiles], role_profiles)
		self.assertEqual(user.bio, ", ".join(role_profiles))
		self.assertEqual(getdate(user.birth_date), date(1990, 5, 17))
		self.assertEqual(user.last_active, datetime(2026, 11, 17, 10, 30))
		self.assertEqual((user.login_after, user.user_image), (0, None))
		self.assertEqual(
			frappe.db.get_value("Currency", answers["name"], "smallest_currency_fraction_value"), 0.25
		)
		error_log = frappe.get_last_doc("Error Log")
		self.assertEqual(json.loads(error_log.error), answers)
		warnings = " ".join(self.message_logs(response, "Warning"))
		self.assertIn("login_after", warnings)
		self.assertIn("user_image", warnings)

	def complete(self, actions: list[dict], flow_json: dict = DEAL_FEEDBACK, answers: dict = RATING):
		flow = self.make_flow(flow_json=flow_json)
		send = self.send_template([flow_button(flow, flow_response_actions=actions)])
		return self.respond(answers, token=f"{send.flow_token}:0")

	def user_values(self, *fields: str) -> tuple:
		values = frappe.db.get_value("User", self.user.name, list(fields), as_dict=True)
		return tuple(values[field] for field in fields)

	def role_profile(self) -> str:
		return (
			frappe.get_doc(
				doctype="Role Profile", role_profile=f"_Test Flow RP {frappe.generate_hash(length=6)}"
			)
			.insert()
			.name
		)

	def message_logs(self, response, level: str) -> list[str]:
		return frappe.get_all(
			"WA Log",
			filters={"reference_doctype": "WA Message", "reference_docname": response.name, "level": level},
			pluck="message",
		)
