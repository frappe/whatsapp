# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# See license.txt

"""Readable text for the Meta errors an admin or agent is likely to hit.

Codes from https://developers.facebook.com/documentation/business-messaging/whatsapp/support/error-codes.
Template errors arrive as code 100 with an `error_subcode`, so subcodes are looked up first.
"""

from frappe import _lt

META_ERRORS = {
	# authorization
	0: _lt("Could not authenticate. Generate a new access token."),
	3: _lt("The Meta app lacks permission for this."),
	10: _lt("Permission missing or revoked in Meta."),
	190: _lt("Access token expired or invalid. Update it on the WA Account."),
	200: _lt("Permission missing or revoked in Meta."),
	# integrity
	368: _lt("Account restricted for a policy violation."),
	130497: _lt("This account cannot message users in this country."),
	131031: _lt("Account locked or restricted. Check WhatsApp Manager."),
	# throttling
	4: _lt("Too many requests. Try again in a few minutes."),
	80007: _lt("Account rate limit reached. Try again in a few minutes."),
	130429: _lt("Sending too fast. Try again shortly."),
	131048: _lt("Sending limited after recipients blocked or reported messages."),
	131056: _lt("Too many messages to this number. Try again shortly."),
	# sending
	1: _lt("Meta could not process the request. Try again later."),
	2: _lt("WhatsApp is temporarily unavailable. Try again later."),
	130403: _lt("You have blocked this user on WhatsApp."),
	131000: _lt("Failed for an unknown reason. Try again."),
	131016: _lt("WhatsApp is temporarily unavailable. Try again later."),
	131021: _lt("Cannot send to the business's own number."),
	131026: _lt("Undeliverable. The number may not be on WhatsApp."),
	131030: _lt("Number not on the test number's allowed list."),
	131042: _lt("Payment method problem. Check billing in Meta."),
	131047: _lt("24-hour window closed. Send a template instead."),
	131049: _lt("Held back by Meta's marketing limit. Try again after 24 hours."),
	131050: _lt("User opted out of marketing messages."),
	131051: _lt("Unsupported message type."),
	131052: _lt("Could not download the user's media. Ask them to resend."),
	131053: _lt("Could not upload the media. Check its type and size."),
	131057: _lt("Account in maintenance mode. Try again shortly."),
	133010: _lt("Phone number not registered on WhatsApp Business."),
	# sending templates
	132000: _lt("Variable count does not match the template."),
	132001: _lt("Template missing in this language, or not approved."),
	132005: _lt("Template too long once variables are filled in."),
	132007: _lt("Template violates a WhatsApp policy."),
	132012: _lt("A variable value has the wrong format."),
	132015: _lt("Template paused for low quality. Edit and resubmit it."),
	132016: _lt("Template disabled. Create a new one."),
	# creating templates (error_subcode)
	2388019: _lt("Limit of 250 templates reached."),
	2388039: _lt("Template under review or edited too often today."),
	2388040: _lt("Part of the template is too long."),
	2388047: _lt("Invalid header format."),
	2388072: _lt("Invalid message format."),
	2388073: _lt("Invalid footer format."),
	2388293: _lt("Too many variables for the message length."),
	2388299: _lt("Variables cannot start or end the template."),
	2494100: _lt("Account in maintenance mode. Try again shortly."),
}


def describe_meta_error(error: dict) -> str | None:
	"""The readable text for one Meta error object, or None when it has nothing to show.

	Meta's own `error_user_msg` is the most specific (it names the field and limit), so it wins.
	"""
	if not isinstance(error, dict):
		return None
	if error.get("error_user_msg"):
		return error["error_user_msg"]
	for code in (error.get("error_subcode"), error.get("code")):
		known = META_ERRORS.get(_permission_range(_as_int(code)))
		if known:
			return str(known)
	return error.get("message") or error.get("error_user_title") or error.get("title")


def _as_int(code) -> int | None:
	try:
		return int(code)
	except (TypeError, ValueError):
		return None


def _permission_range(code: int | None) -> int | None:
	"""Meta reports permission errors anywhere in 200-299."""
	return 200 if code is not None and 200 <= code <= 299 else code
