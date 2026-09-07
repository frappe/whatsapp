# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.email.doctype.notification.notification import (
	get_reference_doctype,
	get_reference_name,
)

from whatsapp.install import WHATSAPP_CHANNEL
from whatsapp.whatsapp.api.utils import log
from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import get_or_create_profile


class WhatsAppNotificationMixin:
	"""Adds the WhatsApp channel to Notification."""

	def validate(self) -> None:
		super().validate()
		if self.channel == WHATSAPP_CHANNEL:
			self._validate_whatsapp()

	def _validate_whatsapp(self) -> None:
		# mandatory_depends_on is only enforced client-side, so the API path arrives here unchecked
		if not self.get("whatsapp_template"):
			frappe.throw(_("WhatsApp Template is required for the WhatsApp channel"))
		if not self.subject:
			frappe.throw(_("Subject is required — it names the notification"))

		template = frappe.get_cached_doc("WhatsApp Template", self.get("whatsapp_template"))
		if template.status != "Approved":
			frappe.throw(
				_("Template {0} is {1} — only Approved templates can be sent").format(
					template.name, template.status
				)
			)
		if template.template_variables and template.reference_doctype != self.document_type:
			frappe.throw(
				_("Template {0} fills its variables from {1}, but this notification runs on {2}").format(
					template.name, template.reference_doctype or _("no Document Type"), self.document_type
				)
			)

	def send_notification_by_channel(self, doc, context) -> None:
		if self.channel != WHATSAPP_CHANNEL:
			return super().send_notification_by_channel(doc, context)

		try:
			self.send_whatsapp_message(doc, context)
			# the base class runs this inside the method we just replaced
			if self.send_system_notification:
				self.create_system_notification(doc, context)
		except Exception:
			log(
				"Error",
				"Message",
				f"Notification {self.name} failed for {doc.doctype} {doc.name}",
				account=self.get("whatsapp_account"),
				reference_doctype=get_reference_doctype(doc),
				reference_docname=get_reference_name(doc),
				traceback=frappe.get_traceback(),
			)

	def send_whatsapp_message(self, doc, context) -> None:
		account = self.get("whatsapp_account") or frappe.db.get_single_value(
			"WhatsApp Settings", "default_account"
		)
		if not account:
			frappe.throw(_("No WhatsApp Account set on the notification or in WhatsApp Settings"))

		numbers = {normalize_phone(number) for number in self.get_receiver_list(doc, context) if number}
		if not numbers:
			return

		for number in numbers:
			profile = get_or_create_profile(number, account)
			frappe.enqueue(
				"whatsapp.whatsapp.notification_channel.send_template_message",
				profile=profile,
				account=account,
				template=self.get("whatsapp_template"),
				reference_doctype=get_reference_doctype(doc),
				reference_docname=get_reference_name(doc),
				enqueue_after_commit=True,
				now=frappe.in_test,
			)


def send_template_message(
	profile: str,
	account: str,
	template: str,
	reference_doctype: str,
	reference_docname: str,
) -> None:
	message = frappe.new_doc("WhatsApp Message")
	message.update(
		{
			"direction": "Outgoing",
			"to": profile,
			"whatsapp_account": account,
			"is_template": 1,
			"whatsapp_template": template,
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
		}
	)
	message.flags.ignore_permissions = True
	message.submit()


def normalize_phone(number: str) -> str:
	# resolve_profile_by_phone matches the stored string exactly, and User.mobile_no is free-form
	return "".join(character for character in number if character.isdigit())
