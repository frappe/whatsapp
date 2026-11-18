# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# See license.txt

import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.api.meta_errors import META_ERRORS
from whatsapp.whatsapp.api.whatsapp import WhatsApp

EXPIRED_TOKEN = {"error": {"message": "Error validating access token", "type": "OAuthException", "code": 190}}
RATE_LIMITED = {
	"error": {"message": "Application request limit reached", "type": "OAuthException", "code": 4}
}


def meta_answers(body: dict, status_code: int = 401) -> MagicMock:
	resp = MagicMock(status_code=status_code, text=json.dumps(body))
	resp.raise_for_status.side_effect = requests.HTTPError(f"{status_code} Client Error")
	return resp


class TestDisconnectOnExpiredToken(IntegrationTestCase):
	def _account(self) -> str:
		return (
			frappe.get_doc(
				doctype="WA Account",
				account_name=f"_Test {self._testMethodName}",
				status="Active",
				phone_id=frappe.generate_hash(length=10),
			)
			.insert()
			.name
		)

	def _client(self, account: str) -> WhatsApp:
		return WhatsApp(
			frappe._dict(
				business_id="waba_1",
				app_id="",
				access_token="token",
				phone_number_id="1",
				account_name=account,
			)
		)

	def _status(self, account: str) -> str:
		return frappe.db.get_value("WA Account", account, "status")

	@patch("whatsapp.whatsapp.api.whatsapp.requests.request")
	def test_error_190_disconnects_the_account_and_explains_why(self, request):
		request.return_value = meta_answers(EXPIRED_TOKEN)
		account = self._account()

		with self.assertRaises(requests.HTTPError) as ctx:
			self._client(account).send_message({"to": "15550100"})

		self.assertEqual(str(ctx.exception), str(META_ERRORS[190]))
		self.assertEqual(self._status(account), "Disconnected")

	@patch("whatsapp.whatsapp.api.whatsapp.requests.post")
	def test_error_190_on_a_media_upload_disconnects_the_account(self, post):
		post.return_value = meta_answers(EXPIRED_TOKEN)
		account = self._account()

		with self.assertRaises(requests.HTTPError):
			self._client(account).upload_media(b"x", "image/png", "x.png")

		self.assertEqual(self._status(account), "Disconnected")

	@patch("whatsapp.whatsapp.api.whatsapp.requests.request")
	def test_other_errors_leave_the_status_alone(self, request):
		account = self._account()
		for body in (RATE_LIMITED, {"error": {"code": 131047}}, {"unexpected": "shape"}):
			request.return_value = meta_answers(body, status_code=400)
			with self.assertRaises(requests.HTTPError):
				self._client(account).get_subscribed_apps()
			self.assertEqual(self._status(account), "Active")


class TestDisconnectSurvivesRollback(IntegrationTestCase):
	@patch("whatsapp.whatsapp.api.whatsapp.requests.request")
	def test_the_status_stays_disconnected_when_the_caller_rolls_back(self, request):
		"""A whitelisted call that throws on the Meta error rolls its request back; the status must survive."""
		request.return_value = meta_answers(EXPIRED_TOKEN)
		default = frappe.db.get_single_value("WA Settings", "default_account")
		account = (
			frappe.get_doc(
				doctype="WA Account",
				account_name=f"_Test rollback {frappe.generate_hash(length=6)}",
				status="Active",
				phone_id=frappe.generate_hash(length=10),
			)
			.insert()
			.name
		)
		frappe.db.commit()

		def cleanup():
			frappe.db.delete("WA Log", {"account": account})
			frappe.db.delete("WA Account", account)
			frappe.db.set_single_value("WA Settings", "default_account", default or "")
			frappe.db.commit()

		self.addCleanup(cleanup)

		with self.assertRaises(requests.HTTPError):
			WhatsApp(
				frappe._dict(access_token="token", phone_number_id="1", account_name=account)
			).send_message({"to": "15550100"})
		frappe.db.rollback()

		self.assertEqual(frappe.db.get_value("WA Account", account, "status"), "Disconnected")
