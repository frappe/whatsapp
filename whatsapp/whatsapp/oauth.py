"""Connect a WhatsApp Business Account with Meta's sign-in, on Frappe Cloud v2 sites.

Central (central.api.oauth) holds Meta's app and its secret; this site reaches it through its own
Pilot. After the code exchange Central relays: access_token, app_id, waba_id, phone_id, pin and
webhook_secret.
"""

import secrets
from urllib.parse import urlencode, urlparse

import frappe
from frappe import _
from frappe.integrations.frappe_providers.cloud_settings import PilotClient, is_v2_site
from frappe.utils.data import escape_html, get_host_name_from_request
from frappe.utils.password import set_encrypted_password
from frappe.www.login import sanitize_redirect
from oauthlib.oauth2 import WebApplicationClient

from whatsapp.whatsapp.api.utils import log

PROVIDER = "meta"
NOTE_TTL = 10 * 60
CALLBACK_PATH = "/api/method/whatsapp.whatsapp.oauth.callback"
DEFAULT_LANDING = "/desk/wa-account"


def _results() -> dict[str, tuple[str, str]]:
	"""Message and indicator for each result code the callback lands with."""
	return {
		"connected": (_("The WhatsApp account {0} is connected."), "green"),
		"reconnected": (_("The WhatsApp account {0} is connected again."), "green"),
		"cancelled": (_("Sign-in was cancelled."), "red"),
		"expired": (_("Sign-in took too long. Please try again."), "red"),
		"not_team_member": (
			_(
				"Only members of this site's Frappe Cloud team can connect a WhatsApp account. Log in to Frappe Cloud in this browser, then try again."
			),
			"red",
		),
		"refused": (_("Meta refused the connection. Please try again."), "red"),
		"wrong_waba": (
			_(
				"You signed in to a different WhatsApp Business Account than the one {0} uses. Sign in to that account, or add the new one as a new WhatsApp account."
			),
			"red",
		),
		"number_in_use": (
			_(
				"You picked a number that another WhatsApp account here already uses. Pick the number {0} uses, or reconnect that other account."
			),
			"red",
		),
		"unavailable": (_("Connect with Meta is only available on Frappe Cloud."), "red"),
		"failed": (_("Couldn't connect the WhatsApp account. Please try again."), "red"),
	}


@frappe.whitelist()
def get_connect_message(result: str, account: str | None = None) -> dict:
	"""The text to show for the `whatsapp_connect` result the callback landed with."""
	message, indicator = _results().get(result) or _results()["failed"]
	# `account` comes from the URL, so it is escaped before it is shown as HTML
	return {"message": message.format(frappe.bold(escape_html(account or ""))), "indicator": indicator}


@frappe.whitelist(methods=["POST"])
def initiate_connect(redirect_to: str = DEFAULT_LANDING, wa_account: str | None = None) -> str:
	"""Start Meta's sign-in and return the link to open. With `wa_account`, the sign-in reconnects it."""
	frappe.only_for("System Manager")
	if not is_v2_site():
		frappe.throw(_results()["unavailable"][0])
	if wa_account:
		frappe.has_permission("WA Account", "write", doc=wa_account, throw=True)

	client = WebApplicationClient(None)
	verifier = client.create_code_verifier(64)
	state = secrets.token_urlsafe(16)
	try:
		link = call_central_method(
			"start",
			provider=PROVIDER,
			state=state,
			code_challenge=client.create_code_challenge(verifier, "S256"),
			return_url=get_host_name_from_request() + CALLBACK_PATH,
		)
	except frappe.ValidationError as e:
		if str(e) != "provider_unavailable":  # Central's code for a provider it has turned off
			raise
		frappe.clear_last_message()
		frappe.throw(_("Connect with Meta isn't available right now"))
	frappe.cache.set_value(
		f"wa_connect:{state}",
		{
			"user": frappe.session.user,
			"verifier": verifier,
			"redirect_to": redirect_to,
			"wa_account": wa_account,
		},
		expires_in_sec=NOTE_TTL,
	)
	return link["authorize_url"]


@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep: guest-whitelisted-method
def callback(
	state: str | None = None,
	code: str | None = None,
	error: str | None = None,
	error_description: str | None = None,
):
	"""Meta sends the user back here through Central; create or update the WA Account."""
	if frappe.session.user == "Guest":
		return _redirect("/login?" + urlencode({"redirect-to": frappe.request.url}))
	if not is_v2_site():
		return land(DEFAULT_LANDING, "unavailable")

	note = frappe.cache.get_value(f"wa_connect:{state}")
	if not note or note["user"] != frappe.session.user:
		return land(DEFAULT_LANDING, "expired")
	frappe.cache.delete_value(f"wa_connect:{state}")

	try:
		result, account = connect(note, code, error, error_description)
	except Exception:
		frappe.db.rollback()
		frappe.log_error("WhatsApp connect with Meta failed")
		result, account = "failed", note["wa_account"]
	# Meta can only send the browser back with a GET, which is rolled back unless it commits;
	# the state note ties this request to the user's own sign-in
	frappe.db.commit()  # nosemgrep
	land(note["redirect_to"], result, account)


def connect(note: dict, code: str | None, error: str | None, error_description: str | None):
	"""Return the result code and the WA Account it is about."""
	wa_account = note["wa_account"]
	if error == "access_denied":
		return "cancelled", wa_account
	if error == "not_team_member":  # from Central: this browser isn't logged in to the site's team
		return "not_team_member", wa_account
	if error:
		frappe.log_error("WhatsApp sign-in with Meta failed", f"{error}: {error_description}")
		return "refused", wa_account

	try:
		token = call_central_method(
			"relay_token",
			provider=PROVIDER,
			grant_type="authorization_code",
			code=code,
			code_verifier=note["verifier"],
		)
	except frappe.ValidationError as e:
		frappe.clear_last_message()
		if str(e) == "invalid_grant":  # Central passes on Meta's error code as the message
			return "expired", wa_account
		frappe.log_error("WhatsApp connect with Meta refused")
		return "refused", wa_account

	if wa_account:
		account = frappe.get_doc("WA Account", wa_account)
		if account.business_id and account.business_id != token["waba_id"]:
			return _refuse("wrong_waba", wa_account, token)
		if account.phone_id != token["phone_id"] and frappe.db.exists(
			"WA Account", {"phone_id": token["phone_id"]}
		):
			return _refuse("number_in_use", wa_account, token)
	elif same_number := frappe.db.exists("WA Account", {"phone_id": token["phone_id"]}):
		account = frappe.get_doc("WA Account", same_number)
	else:
		account = frappe.new_doc("WA Account", account_name=token["phone_id"])

	account.update(
		{
			"access_token": token["access_token"],
			"app_id": token["app_id"],
			"business_id": token["waba_id"],
			"phone_id": token["phone_id"],
			"two_step_pin": token["pin"],
			"webhook_secret": token["webhook_secret"],
			"connected_with_meta": 1,
			"status": "Active",
		}
	)
	account.save()
	_store_new_secrets(token, skip=account.name)
	return ("reconnected" if wa_account else "connected"), account.name


def _refuse(result: str, wa_account: str, token: dict) -> tuple[str, str]:
	"""Central changed the secrets of what was signed in to before this refusal; keep them in step."""
	_store_new_secrets(token)
	_disconnect_unused(token["waba_id"])
	return result, wa_account


def _store_new_secrets(token: dict, skip: str = "") -> None:
	"""Each sign-in gives the WABA a new webhook secret and the number a new PIN; store them on the
	other accounts that use them, or their relayed webhooks fail the signature check."""
	for other in frappe.get_all(
		"WA Account", {"business_id": token["waba_id"], "name": ("!=", skip)}, pluck="name"
	):
		set_encrypted_password("WA Account", other, token["webhook_secret"], "webhook_secret")
	if number := frappe.db.get_value("WA Account", {"phone_id": token["phone_id"], "name": ("!=", skip)}):
		set_encrypted_password("WA Account", number, token["pin"], "two_step_pin")


def disconnect(waba_id: str) -> None:
	"""Ask Central to stop sending this WABA's webhooks here. A failure is logged, not raised."""
	try:
		call_central_method("disconnect", waba_id=waba_id)
	except frappe.ValidationError as e:
		frappe.clear_last_message()
		log("Warning", "API", f"Could not stop Frappe Cloud sending the webhooks of WABA {waba_id}: {e}")


def _disconnect_unused(waba_id: str) -> None:
	"""Central already routed the WABA signed in to here; drop that route if no account uses it."""
	if not frappe.db.exists("WA Account", {"business_id": waba_id}):
		disconnect(waba_id)


def call_central_method(method: str, **data) -> dict:
	"""Call Central's central.api.oauth.<method> through this site's Pilot."""
	client = PilotClient()
	return client.post(client.site_path(f"central/central.api.oauth.{method}"), data)


def land(redirect_to: str, result: str, account: str | None = None) -> None:
	url = urlparse(sanitize_redirect(redirect_to))
	query = urlencode({"whatsapp_connect": result} | ({"whatsapp_account": account} if account else {}))
	_redirect(url._replace(query=f"{url.query}&{query}" if url.query else query).geturl())


def _redirect(location: str) -> None:
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = location
