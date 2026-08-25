# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
import secrets
from unittest.mock import patch

import frappe
from frappe.email.doctype.notification.notification import clear_notification_cache
from frappe.tests import IntegrationTestCase

from whatsapp.install import setup_notification_channel
from whatsapp.whatsapp.notification_channel import normalize_phone


class IntegrationTestNotificationChannel(IntegrationTestCase):
	"""The WhatsApp channel added to the stock Notification doctype."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self._make_settings()
		self._silence_other_todo_notifications()

	# -------------------------------------------------------------------------
	# helpers
	# -------------------------------------------------------------------------

	def _silence_other_todo_notifications(self) -> None:
		"""The module runs in one transaction, so rules built by earlier tests are still visible
		here — as are whatever rules the site already has on ToDo."""
		frappe.db.set_value(
			"Notification", {"document_type": "ToDo", "enabled": 1}, "enabled", 0, update_modified=False
		)
		clear_notification_cache()

	def _make_settings(self) -> None:
		settings = frappe.get_single("WhatsApp Settings")
		settings.whatsapp_api_url = "https://graph.facebook.com"
		settings.whatsapp_api_version = "v22.0"
		settings.save()

	def _make_account(self) -> str:
		uid = frappe.generate_hash(length=6)
		return (
			frappe.get_doc(
				doctype="WhatsApp Account",
				account_name=f"_Test Notif Account {uid}",
				status="Active",
				phone_id=f"phone_{uid}",
				business_id="test_business",
				app_id="test_app",
				access_token="test_token",
			)
			.insert()
			.name
		)

	def _make_template(self, account: str, **overrides) -> str:
		uid = frappe.generate_hash(length=6)
		data = dict(
			doctype="WhatsApp Template",
			template_label=f"_Test Notif Template {uid}",
			template_name=f"_test_notif_template_{uid}",
			template_type="Utility",
			language="en_US",
			message="Reminder: {{description}}",
			whatsapp_account=account,
			whatsapp_template_id=uid,
			status="Approved",
			variable_format="Named",
			reference_doctype="ToDo",
			template_variables=[
				{
					"variable_name": "description",
					"variable_example": "Buy milk",
					"variable_field": "description",
				}
			],
		)
		data.update(overrides)
		return frappe.get_doc(data).insert().name

	def _make_notification(self, **overrides) -> str:
		uid = frappe.generate_hash(length=6)
		data = dict(
			doctype="Notification",
			subject=f"_Test WhatsApp Notification {uid}",
			document_type="ToDo",
			event="New",
			channel="WhatsApp",
			enabled=1,
			recipients=[{"receiver_by_role": "Administrator"}],
		)
		data.update(overrides)
		return frappe.get_doc(data).insert().name

	def _make_todo(self, description: str = "Ship the release") -> str:
		return frappe.get_doc(doctype="ToDo", description=description).insert().name

	def _set_admin_mobile(self) -> str:
		"""Give Administrator a fresh number per test and return its digits.

		Reusing one number across tests collides on WhatsApp Profile's autoname once a second
		account is involved — see get_or_create_profile."""
		digits = f"9198{secrets.randbelow(10**8):08d}"
		frappe.db.set_value("User", "Administrator", "mobile_no", f"+{digits[:2]} {digits[2:7]} {digits[7:]}")
		return digits

	def _messages_for(self, todo: str) -> list[dict]:
		return frappe.get_all(
			"WhatsApp Message",
			filters={"reference_doctype": "ToDo", "reference_docname": todo},
			fields=["name", "to", "status", "is_template", "whatsapp_template", "template_body_parameters"],
		)

	# -------------------------------------------------------------------------
	# setup / schema
	# -------------------------------------------------------------------------

	def test_channel_option_and_custom_fields_exist(self):
		meta = frappe.get_meta("Notification")
		self.assertIn("WhatsApp", meta.get_field("channel").options.split("\n"))
		self.assertTrue(meta.get_field("whatsapp_template"))
		self.assertTrue(meta.get_field("whatsapp_account"))

	def test_subject_stays_visible_and_message_section_hides(self):
		"""Notification.autoname is `subject or notification_title` — a hidden Subject would
		leave every WhatsApp rule with a hash name."""
		meta = frappe.get_meta("Notification")
		self.assertIn("WhatsApp", meta.get_field("subject").depends_on)
		self.assertIn("WhatsApp", meta.get_field("subject").mandatory_depends_on)
		self.assertIn("!= 'WhatsApp'", meta.get_field("message_sb").depends_on)

	def test_setup_is_idempotent(self):
		setup_notification_channel()
		setup_notification_channel()

		for fieldname, property_name in (("channel", "options"), ("subject", "depends_on")):
			self.assertEqual(
				frappe.db.count(
					"Property Setter",
					{"doc_type": "Notification", "field_name": fieldname, "property": property_name},
				),
				1,
			)

		options = frappe.get_meta("Notification").get_field("channel").options
		self.assertEqual(options.split("\n").count("WhatsApp"), 1)

	# -------------------------------------------------------------------------
	# dispatch
	# -------------------------------------------------------------------------

	@patch("frappe.email.doctype.notification.notification.Notification.send_an_email")
	def test_email_channel_is_untouched(self, mock_email):
		self._make_notification(
			channel="Email",
			message="Plain body",
			recipients=[{"receiver_by_role": "Administrator"}],
		)
		self._make_todo()

		mock_email.assert_called_once()

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_whatsapp_channel_sends_template_message(self, mock_send):
		mock_send.return_value = {"messages": [{"id": "wamid.notif_test"}]}
		mobile = self._set_admin_mobile()
		account = self._make_account()
		template = self._make_template(account)
		self._make_notification(whatsapp_template=template, whatsapp_account=account)

		todo = self._make_todo("Ship the release")

		messages = self._messages_for(todo)
		self.assertEqual(len(messages), 1)
		self.assertEqual(messages[0].is_template, 1)
		self.assertEqual(messages[0].whatsapp_template, template)
		self.assertEqual(messages[0].status, "Sent")

		profile = frappe.get_doc("WhatsApp Profile", messages[0].to)
		self.assertEqual(profile.phone_number, mobile)

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_template_variables_come_from_the_triggering_document(self, mock_send):
		mock_send.return_value = {"messages": [{"id": "wamid.vars"}]}
		self._set_admin_mobile()
		account = self._make_account()
		template = self._make_template(account)
		self._make_notification(whatsapp_template=template, whatsapp_account=account)

		todo = self._make_todo("Renew the domain")

		body = json.loads(self._messages_for(todo)[0].template_body_parameters or "{}")
		self.assertEqual(body, {"description": "Renew the domain"})

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_account_falls_back_to_default_when_blank(self, mock_send):
		mock_send.return_value = {"messages": [{"id": "wamid.default_account"}]}
		self._set_admin_mobile()
		account = self._make_account()
		frappe.db.set_single_value("WhatsApp Settings", "default_account", account)
		template = self._make_template(account)
		self._make_notification(whatsapp_template=template)

		todo = self._make_todo()

		self.assertEqual(len(self._messages_for(todo)), 1)

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_differently_formatted_numbers_collapse_to_one_profile(self, mock_send):
		mock_send.return_value = {"messages": [{"id": "wamid.dedupe"}]}
		mobile = self._set_admin_mobile()
		account = self._make_account()
		template = self._make_template(account)

		uid = frappe.generate_hash(length=6)
		role = frappe.get_doc(doctype="Role", role_name=f"_Test WA Role {uid}").insert().name
		frappe.get_doc(
			doctype="User",
			email=f"_test_wa_{uid}@example.com",
			first_name="Test WA",
			mobile_no=mobile,
			roles=[{"role": role}],
		).insert()

		self._make_notification(
			whatsapp_template=template,
			whatsapp_account=account,
			recipients=[{"receiver_by_role": "Administrator"}, {"receiver_by_role": role}],
		)

		todo = self._make_todo()

		self.assertEqual(len(self._messages_for(todo)), 1)
		self.assertEqual(
			frappe.db.count(
				"WhatsApp Profile",
				{"phone_number": mobile, "whatsapp_account": account},
			),
			1,
		)

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_no_recipients_sends_nothing(self, mock_send):
		frappe.db.set_value("User", "Administrator", "mobile_no", None)
		account = self._make_account()
		template = self._make_template(account)
		self._make_notification(whatsapp_template=template, whatsapp_account=account)

		todo = self._make_todo()

		self.assertEqual(self._messages_for(todo), [])
		mock_send.assert_not_called()

	# -------------------------------------------------------------------------
	# validation
	# -------------------------------------------------------------------------

	def test_template_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			self._make_notification()

	def test_unapproved_template_is_rejected(self):
		account = self._make_account()
		template = self._make_template(account, status="Pending")
		with self.assertRaises(frappe.ValidationError):
			self._make_notification(whatsapp_template=template, whatsapp_account=account)

	def test_template_reference_doctype_must_match_document_type(self):
		account = self._make_account()
		template = self._make_template(account, reference_doctype="User")
		with self.assertRaises(frappe.ValidationError):
			self._make_notification(whatsapp_template=template, whatsapp_account=account)

	# -------------------------------------------------------------------------
	# failure handling
	# -------------------------------------------------------------------------

	@patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message")
	def test_send_failure_is_logged_and_does_not_break_the_trigger(self, mock_send):
		from requests import HTTPError

		mock_send.side_effect = HTTPError("API Error: Rate limit exceeded")
		self._set_admin_mobile()
		account = self._make_account()
		template = self._make_template(account)
		notification = self._make_notification(whatsapp_template=template, whatsapp_account=account)

		todo = self._make_todo()

		self.assertTrue(frappe.db.exists("ToDo", todo))
		self.assertTrue(
			frappe.db.exists(
				"WhatsApp Log",
				{"level": "Error", "message": ("like", f"%{notification}%")},
			)
		)

	def test_normalize_phone_keeps_digits_only(self):
		self.assertEqual(normalize_phone("+91 (98765) 43210"), "919876543210")
