# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.notification.whatsapp_message_received.whatsapp_message_received import (
	PREVIEW_LIMIT,
	_message_preview,
)

STANDARD_NOTIFICATIONS = (
	"WhatsApp Message Received",
	"WhatsApp Message Sent",
	"WhatsApp Message Send Failed",
	"WhatsApp Message Status Updated",
	"WhatsApp Template Approved",
	"WhatsApp Template Rejected",
)


def _message(message="", mime_type=None):
	return frappe._dict(message=message, mime_type=mime_type)


class IntegrationTestMessagePreview(IntegrationTestCase):
	def test_text_is_returned_as_is(self):
		self.assertEqual(_message_preview(_message("Is the booking confirmed?")), "Is the booking confirmed?")

	def test_html_is_stripped(self):
		self.assertEqual(_message_preview(_message("<b>Bold</b> and <i>italic</i>")), "Bold and italic")

	def test_long_text_is_truncated_with_an_ellipsis(self):
		preview = _message_preview(_message("x" * 300))
		self.assertEqual(len(preview), PREVIEW_LIMIT + 1)
		self.assertTrue(preview.endswith("…"))

	def test_short_text_keeps_no_ellipsis(self):
		self.assertFalse(_message_preview(_message("x" * PREVIEW_LIMIT)).endswith("…"))

	def test_media_is_named_rather_than_called_media(self):
		for mime_type, expected in (
			("image/jpeg", "Photo"),
			("image/webp", "Photo"),
			("video/mp4", "Video"),
			("audio/ogg", "Audio message"),
			("application/pdf", "Document"),
		):
			with self.subTest(mime_type=mime_type):
				self.assertEqual(_message_preview(_message(mime_type=mime_type)), expected)

	def test_reaction_previews_as_the_emoji(self):
		self.assertEqual(_message_preview(_message("👍")), "👍")

	def test_empty_message_without_media_previews_as_blank(self):
		self.assertEqual(_message_preview(_message()), "")


class IntegrationTestStandardNotifications(IntegrationTestCase):
	def test_every_rule_sets_an_in_app_title_and_message(self):
		"""create_system_notification takes description ONLY from notification_message —
		a blank one leaves NotificationLog to backfill it with the email HTML."""
		for name in STANDARD_NOTIFICATIONS:
			with self.subTest(notification=name):
				rule = frappe.get_doc("Notification", name)
				self.assertTrue(rule.notification_title, f"{name} has no notification_title")
				self.assertTrue(rule.notification_message, f"{name} has no notification_message")
