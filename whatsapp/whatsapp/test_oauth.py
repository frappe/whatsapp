from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import frappe
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request

from whatsapp.install import disconnect_meta_accounts
from whatsapp.whatsapp import oauth

V2 = {"pilot_endpoint": "http://pilot.test", "pilot_auth_token": "pt"}
NOT_V2 = {"pilot_endpoint": None, "pilot_auth_token": None}
LINK = {"authorize_url": "https://www.facebook.com/dialog/oauth?x=1", "client_id": "cid", "scopes": []}


def pilot_path(method: str) -> str:
	return f"sites/{frappe.local.site}/central/central.api.oauth.{method}"


def relayed(waba_id: str = "waba_oauth_1", phone_id: str = "phone_oauth_1") -> dict:
	return {
		"access_token": "meta-token",
		"app_id": "fc-app",
		"waba_id": waba_id,
		"phone_id": phone_id,
		"pin": "123456",
		"webhook_secret": "route-secret",
	}


def landed() -> dict:
	location = urlparse(frappe.local.response["location"])
	return {"path": location.path} | {k: v[0] for k, v in parse_qs(location.query).items()}


class TestCanConnectWithMeta(IntegrationTestCase):
	def setUp(self):
		oauth.get_active_providers.clear_cache()
		self.addCleanup(oauth.get_active_providers.clear_cache)
		frappe.cache.delete_value(oauth.PROVIDERS_DOWN_KEY)
		self.addCleanup(frappe.cache.delete_value, oauth.PROVIDERS_DOWN_KEY)
		self.pilot: MagicMock = self.enterContext(
			patch.object(oauth.PilotClient, "post", return_value={"meta": None, "google": "gid"})
		)

	def test_a_v2_site_with_meta_turned_on_shows_the_button(self):
		with patch.dict(frappe.conf, V2):
			self.assertTrue(oauth.can_connect_with_meta())
		self.assertEqual(self.pilot.call_args.args[0], pilot_path("get_active_providers"))

	def test_meta_turned_off_or_central_down_hides_it(self):
		self.pilot.return_value = {"google": "gid"}
		with patch.dict(frappe.conf, V2):
			self.assertFalse(oauth.can_connect_with_meta())
			oauth.get_active_providers.clear_cache()
			self.pilot.side_effect = frappe.ValidationError("down")
			self.assertFalse(oauth.can_connect_with_meta())

	def test_central_down_is_asked_once_a_minute_not_on_every_call(self):
		self.pilot.side_effect = frappe.ValidationError("down")
		with patch.dict(frappe.conf, V2), patch.object(frappe, "log_error") as log_error:
			self.assertFalse(oauth.can_connect_with_meta())
			self.assertFalse(oauth.can_connect_with_meta())
		self.pilot.assert_called_once()
		log_error.assert_called_once()

	def test_a_site_off_frappe_cloud_never_asks_central(self):
		with patch.dict(frappe.conf, NOT_V2):
			self.assertFalse(oauth.can_connect_with_meta())
		self.pilot.assert_not_called()

	def test_an_agent_does_not_see_it(self):
		with (
			patch.dict(frappe.conf, V2),
			self.set_user(create_user("wa-oauth-agent@example.com", "Agent").name),
		):
			self.assertFalse(oauth.can_connect_with_meta())


class TestInitiateConnect(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, V2))
		self.pilot: MagicMock = self.enterContext(patch.object(oauth.PilotClient, "post", return_value=LINK))
		set_request(method="POST", base_url="http://hd.localhost:8000")

	def test_asks_central_to_start_meta_and_keeps_the_verifier(self):
		self.assertEqual(oauth.initiate_connect("/helpdesk/whatsapp"), LINK["authorize_url"])

		path, data = self.pilot.call_args.args
		self.assertEqual(path, pilot_path("start"))
		self.assertEqual(data["provider"], "meta")
		self.assertEqual(data["return_url"], "http://hd.localhost:8000" + oauth.CALLBACK_PATH)
		note = frappe.cache.get_value(f"wa_connect:{data['state']}")
		self.assertEqual(
			{k: note[k] for k in ("user", "redirect_to", "wa_account")},
			{"user": "Administrator", "redirect_to": "/helpdesk/whatsapp", "wa_account": None},
		)
		self.assertTrue(note["verifier"])

	def test_reconnect_keeps_the_account_in_the_note(self):
		account = make_account("Reconnect note", "waba_note")
		oauth.initiate_connect(wa_account=account.name)

		note = frappe.cache.get_value(f"wa_connect:{self.pilot.call_args.args[1]['state']}")
		self.assertEqual(note["wa_account"], account.name)

	def test_a_site_without_pilot_credentials_is_refused(self):
		with patch.dict(frappe.conf, NOT_V2):
			with self.assertRaisesRegex(frappe.ValidationError, "only available on Frappe Cloud"):
				oauth.initiate_connect()
		self.pilot.assert_not_called()

	def test_only_a_system_manager_can_connect(self):
		with self.set_user(create_user("wa-oauth-agent@example.com", "Agent").name):
			self.assertRaises(frappe.PermissionError, oauth.initiate_connect)
		self.pilot.assert_not_called()

	def test_a_turned_off_provider_gives_a_clear_message(self):
		self.pilot.side_effect = frappe.ValidationError("provider_unavailable")
		with self.assertRaisesRegex(frappe.ValidationError, "isn't available right now"):
			oauth.initiate_connect()


class TestCallback(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, V2))
		self.enterContext(patch.object(frappe.db, "commit"))
		self.pilot: MagicMock = self.enterContext(
			patch.object(oauth.PilotClient, "post", return_value=relayed())
		)
		set_request(method="GET", base_url="http://hd.localhost:8000", path=oauth.CALLBACK_PATH)
		frappe.db.delete("WA Account", {"business_id": ("like", "waba_oauth%")})

	def note(self, wa_account: str | None = None) -> str:
		state = frappe.generate_hash()
		frappe.cache.set_value(
			f"wa_connect:{state}",
			{
				"user": "Administrator",
				"verifier": "v" * 64,
				"redirect_to": "/desk/wa-account",
				"wa_account": wa_account,
			},
			expires_in_sec=60,
		)
		return state

	def test_connect_creates_the_account_from_the_relay_result(self):
		oauth.callback(state=self.note(), code="the-code")

		path, data = self.pilot.call_args.args
		self.assertEqual(path, pilot_path("relay_token"))
		self.assertEqual(
			data,
			{
				"provider": "meta",
				"grant_type": "authorization_code",
				"code": "the-code",
				"code_verifier": "v" * 64,
			},
		)
		account = frappe.get_doc("WA Account", {"phone_id": "phone_oauth_1"})
		self.assertEqual(
			(account.app_id, account.business_id, account.status, account.connected_with_meta),
			("fc-app", "waba_oauth_1", "Active", 1),
		)
		self.assertEqual(account.get_password("access_token"), "meta-token")
		self.assertEqual(account.get_password("two_step_pin"), "123456")
		self.assertEqual(account.get_password("webhook_secret"), "route-secret")
		self.assertEqual(
			landed(),
			{"path": "/desk/wa-account", "whatsapp_connect": "connected", "whatsapp_account": account.name},
		)

	def test_a_new_account_is_named_after_the_business_and_number(self):
		for extra, name in (
			(
				{"verified_name": "Acme Store", "display_phone_number": "+1 555-0100"},
				"Acme Store (+1 555-0100)",
			),
			({"display_phone_number": "+1 555-0100"}, "+1 555-0100"),
			({"verified_name": "Acme Store"}, "phone_oauth_1"),
			(
				{"verified_name": "Tom & Jerry <Shop>", "display_phone_number": "+1 555-0100"},
				"Tom & Jerry Shop (+1 555-0100)",
			),
			({"verified_name": "<>", "display_phone_number": "+1 555-0100"}, "+1 555-0100"),
			(
				{"verified_name": "A" * 200, "display_phone_number": "+1 555-0100"},
				"A" * 106 + " (+1 555-0100)",
			),
		):
			with self.subTest(name):
				frappe.db.delete("WA Account", {"business_id": "waba_oauth_1"})
				self.pilot.return_value = relayed() | extra
				oauth.callback(state=self.note(), code="the-code")
				self.assertEqual(landed()["whatsapp_account"], name)
				self.assertEqual(frappe.db.get_value("WA Account", {"phone_id": "phone_oauth_1"}), name)

	def test_a_readable_name_another_account_has_gets_a_number(self):
		frappe.get_doc(
			doctype="WA Account", account_name="Acme Store (+1 555-0100)", business_id="waba_oauth_other"
		).insert()
		self.pilot.return_value = relayed() | {
			"verified_name": "Acme Store",
			"display_phone_number": "+1 555-0100",
		}

		oauth.callback(state=self.note(), code="the-code")

		self.assertEqual(landed()["whatsapp_account"], "Acme Store (+1 555-0100)-1")

	def test_reconnect_keeps_the_account_name(self):
		account = make_account("Keep name", "waba_oauth_1", phone_id="phone_oauth_1")
		self.pilot.return_value = relayed() | {
			"verified_name": "Acme Store",
			"display_phone_number": "+1 555-0100",
		}

		oauth.callback(state=self.note(account.name), code="the-code")

		self.assertEqual(landed()["whatsapp_connect"], "reconnected")
		self.assertEqual(frappe.db.get_value("WA Account", {"phone_id": "phone_oauth_1"}), account.name)

	def test_reconnect_updates_the_same_account(self):
		account = make_account("Reconnect", "waba_oauth_1", status="Inactive")

		oauth.callback(state=self.note(account.name), code="the-code")

		account.reload()
		self.assertEqual((account.status, account.connected_with_meta), ("Active", 1))
		self.assertEqual(account.get_password("access_token"), "meta-token")
		self.assertEqual(frappe.db.count("WA Account", {"business_id": "waba_oauth_1"}), 1)
		self.assertEqual(landed()["whatsapp_connect"], "reconnected")

	def test_reconnect_to_a_different_waba_is_refused(self):
		account = make_account("Other WABA", "waba_oauth_old")

		oauth.callback(state=self.note(account.name), code="the-code")

		account.reload()
		self.assertEqual((account.business_id, account.connected_with_meta), ("waba_oauth_old", 0))
		self.assertEqual(landed()["whatsapp_connect"], "wrong_waba")
		path, data = self.pilot.call_args.args
		self.assertEqual((path, data), (pilot_path("disconnect"), {"waba_id": "waba_oauth_1"}))

	def test_a_refused_reconnect_keeps_the_new_secrets_of_the_waba_signed_in_to(self):
		account = make_account("Other WABA", "waba_oauth_old")
		other = make_account("Signed in", "waba_oauth_1", phone_id="phone_oauth_1")

		oauth.callback(state=self.note(account.name), code="the-code")

		self.assertEqual(landed()["whatsapp_connect"], "wrong_waba")
		self.assertEqual(other.get_password("webhook_secret"), "route-secret")
		self.assertEqual(other.get_password("two_step_pin"), "123456")
		self.assertNotIn(pilot_path("disconnect"), [c.args[0] for c in self.pilot.call_args_list])

	def test_reconnect_to_a_number_another_account_uses_is_refused(self):
		account = make_account("Reconnect", "waba_oauth_1")
		other = make_account("Same WABA", "waba_oauth_1", phone_id="phone_oauth_1")

		oauth.callback(state=self.note(account.name), code="the-code")

		self.assertEqual(landed()["whatsapp_connect"], "number_in_use")
		account.reload()
		self.assertEqual((account.phone_id, account.connected_with_meta), ("phone Reconnect", 0))
		self.assertEqual(frappe.db.count("WA Account", {"phone_id": "phone_oauth_1"}), 1)
		self.assertEqual(other.get_password("two_step_pin"), "123456")

	def test_other_numbers_on_the_waba_get_the_new_webhook_secret(self):
		other = make_account("Second number", "waba_oauth_1")

		oauth.callback(state=self.note(), code="the-code")

		self.assertEqual(other.get_password("webhook_secret"), "route-secret")

	def test_a_number_a_reconnect_moved_away_from_can_be_connected_again(self):
		# named after phone_oauth_1, then reconnected to another number of the same WABA
		moved = frappe.get_doc(
			doctype="WA Account",
			account_name="phone_oauth_1",
			business_id="waba_oauth_1",
			phone_id="phone_oauth_2",
			access_token="old-token",
			status="Active",
		).insert()

		oauth.callback(state=self.note(), code="the-code")

		self.assertEqual(landed()["whatsapp_connect"], "connected")
		self.assertEqual(frappe.db.get_value("WA Account", {"phone_id": "phone_oauth_1"}), "phone_oauth_1-1")
		self.assertEqual(moved.get_password("webhook_secret"), "route-secret")

	def test_a_failure_after_the_relay_keeps_the_new_secrets(self):
		other = make_account("Second number", "waba_oauth_1")

		# the account to reconnect was deleted after the sign-in started
		oauth.callback(state=self.note("_Test OAuth Deleted"), code="the-code")

		self.assertEqual(landed()["whatsapp_connect"], "failed")
		self.assertEqual(other.get_password("webhook_secret"), "route-secret")
		self.assertNotIn(pilot_path("disconnect"), [c.args[0] for c in self.pilot.call_args_list])

	def test_sign_in_errors_land_with_their_result(self):
		for error, result in (
			("access_denied", "cancelled"),
			("not_team_member", "not_team_member"),
			("server_error", "refused"),
		):
			with self.subTest(error):
				oauth.callback(state=self.note(), error=error)
				self.assertEqual(landed()["whatsapp_connect"], result)
		self.pilot.assert_not_called()

	def test_relay_errors_land_with_their_result(self):
		for message, result in (
			("invalid_grant", "expired"),
			("waba_in_use", "waba_in_use"),
			("no_phone_number", "no_phone_number"),
			("no_waba", "no_waba"),
			("phone_number_unclear", "phone_number_unclear"),
			("pin_changed", "pin_changed"),
			("Meta refused the request: boom", "refused"),
		):
			with self.subTest(message):
				self.pilot.side_effect = frappe.ValidationError(message)
				oauth.callback(state=self.note(), code="the-code")
				self.assertEqual(landed()["whatsapp_connect"], result)
		self.assertFalse(frappe.db.exists("WA Account", {"phone_id": "phone_oauth_1"}))

	def test_an_unknown_state_lands_as_expired(self):
		oauth.callback(state="nope", code="the-code")

		self.assertEqual(landed(), {"path": "/desk/wa-account", "whatsapp_connect": "expired"})
		self.pilot.assert_not_called()

	def test_a_site_without_pilot_credentials_is_refused(self):
		with patch.dict(frappe.conf, NOT_V2):
			oauth.callback(state=self.note(), code="the-code")

		self.assertEqual(landed()["whatsapp_connect"], "unavailable")
		self.pilot.assert_not_called()

	def test_a_guest_is_sent_to_log_in_first(self):
		with self.set_user("Guest"):
			oauth.callback(state="s", code="c")

		self.assertTrue(frappe.local.response["location"].startswith("/login?redirect-to="))

	def test_each_central_refusal_has_its_own_message(self):
		self.assertEqual(
			oauth.CENTRAL_REFUSALS,
			("waba_in_use", "no_waba", "no_phone_number", "phone_number_unclear", "pin_changed"),
		)
		messages = {code: oauth.get_connect_message(code)["message"] for code in oauth.CENTRAL_REFUSALS}
		self.assertEqual(len(set(messages.values())), len(messages))
		for general in ("failed", "refused"):
			self.assertNotIn(oauth.get_connect_message(general)["message"], messages.values())

	def test_the_message_escapes_the_account_from_the_url(self):
		message = oauth.get_connect_message("connected", "<img src=x onerror=alert(1)>")["message"]

		self.assertNotIn("<img", message)


class TestDeleteMetaAccount(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, V2))
		self.pilot: MagicMock = self.enterContext(patch.object(oauth.PilotClient, "post", return_value={}))
		self.client: MagicMock = self.enterContext(
			patch("whatsapp.whatsapp.doctype.wa_account.wa_account._get_whatsapp_client")
		)
		# another account is the default, so these accounts can be deleted when others exist on the site
		frappe.db.set_single_value("WA Settings", "default_account", "_Test OAuth Default")

	def test_delete_unsubscribes_and_tells_central(self):
		account = make_account("Delete Meta", "waba_oauth_delete", connected_with_meta=1)

		account.delete()

		self.client.return_value.unsubscribe_app.assert_called_once_with()
		self.pilot.assert_called_once_with(pilot_path("disconnect"), {"waba_id": "waba_oauth_delete"})

	def test_a_central_failure_does_not_stop_the_delete(self):
		self.pilot.side_effect = frappe.ValidationError("Could not reach your server")
		account = make_account("Delete Meta down", "waba_oauth_down", connected_with_meta=1)

		account.delete()

		self.assertFalse(frappe.db.exists("WA Account", account.name))

	def test_a_manual_account_does_not_call_central(self):
		account = make_account("Delete manual", "waba_oauth_manual")

		account.delete()

		self.client.return_value.unsubscribe_app.assert_called_once_with()
		self.pilot.assert_not_called()


def make_account(name: str, business_id: str, **values):
	return frappe.get_doc(
		doctype="WA Account",
		account_name=f"_Test OAuth {name}",
		business_id=business_id,
		access_token="old-token",
		**{"status": "Active", "phone_id": f"phone {name}"} | values,
	).insert()


class TestUninstall(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, V2))
		self.pilot: MagicMock = self.enterContext(patch.object(oauth.PilotClient, "post", return_value={}))
		frappe.db.delete("WA Account", {"business_id": ("like", "waba_oauth%")})

	def test_uninstall_disconnects_each_meta_waba_once(self):
		make_account("Uninstall A", "waba_oauth_a", connected_with_meta=1)
		make_account("Uninstall A2", "waba_oauth_a", connected_with_meta=1)
		make_account("Uninstall B", "waba_oauth_b", connected_with_meta=1)
		make_account("Uninstall manual", "waba_oauth_manual")

		disconnect_meta_accounts()

		disconnected = [c.args[1]["waba_id"] for c in self.pilot.call_args_list]
		self.assertEqual(
			sorted(w for w in disconnected if w.startswith("waba_oauth")), ["waba_oauth_a", "waba_oauth_b"]
		)
		self.assertEqual(len(disconnected), len(set(disconnected)))
		self.assertEqual({c.args[0] for c in self.pilot.call_args_list}, {pilot_path("disconnect")})

	def test_a_central_failure_is_logged_and_does_not_stop_the_uninstall(self):
		make_account("Uninstall down", "waba_oauth_down", connected_with_meta=1)
		self.pilot.side_effect = frappe.ValidationError("Could not reach your server")

		with patch.object(frappe, "log_error") as log_error:
			disconnect_meta_accounts()

		self.assertIn(
			"Couldn't stop Frappe Cloud relaying the webhooks of WABA waba_oauth_down",
			[c.args[0] for c in log_error.call_args_list],
		)
