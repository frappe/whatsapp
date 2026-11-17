# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# See license.txt

"""Readable text for the Meta errors an admin or agent is likely to hit.

Codes from https://developers.facebook.com/documentation/business-messaging/whatsapp/support/error-codes.
Template errors arrive as code 100 with an `error_subcode`, so subcodes are looked up first.
"""

from frappe import _, _lt

# General docs, not a per-error page: the user searches from there.
DOCS_URL = "https://developers.facebook.com/documentation/business-messaging/whatsapp"

META_ERRORS = {
	# authorization
	0: _lt("WhatsApp could not authenticate this account. Generate a new access token for the WA Account."),
	3: _lt("The Meta app lacks the permission for this action. Check the app's permissions in Meta."),
	10: _lt(
		"Permission for this action was not granted or was removed. Check the app's permissions in Meta."
	),
	190: _lt("The access token has expired or is invalid. Update the access token on the WA Account."),
	200: _lt(
		"Permission for this action was not granted or was removed. Check the app's permissions in Meta."
	),
	# integrity
	368: _lt(
		"The WhatsApp Business account is restricted for a policy violation. Check it in WhatsApp Manager."
	),
	130497: _lt("This WhatsApp Business account cannot message users in this country."),
	131031: _lt("The WhatsApp Business account is locked or restricted. Check it in WhatsApp Manager."),
	# throttling
	4: _lt("Too many requests to Meta. Wait a few minutes and try again."),
	80007: _lt("The WhatsApp Business account reached its rate limit. Wait a few minutes and try again."),
	130429: _lt("Messages are being sent too fast. Wait a moment and try again."),
	131048: _lt(
		"Sending is limited because recipients blocked or reported recent messages. Check quality in WhatsApp Manager."
	),
	131056: _lt("Too many messages to this number in a short time. Wait a moment and try again."),
	# sending
	1: _lt("Meta could not process the request. Try again later."),
	2: _lt("WhatsApp is temporarily unavailable. Try again later."),
	130403: _lt("Your business has blocked this user on WhatsApp. Unblock them to send messages."),
	131000: _lt("The message failed for an unknown reason. Try again."),
	131016: _lt("WhatsApp is temporarily unavailable. Try again later."),
	131021: _lt("The recipient is the business's own number. Send to a different number."),
	131026: _lt(
		"The message could not be delivered. The number may not use WhatsApp, or needs to update the app."
	),
	131030: _lt(
		"This number is not on the test number's allowed list. Add it in Meta, or use a production number."
	),
	131042: _lt(
		"There is a problem with the WhatsApp Business account's payment method. Check billing in Meta."
	),
	131047: _lt(
		"More than 24 hours have passed since the customer's last reply. Send an approved template instead."
	),
	131049: _lt(
		"Meta held back this marketing message to limit how many the user gets. Try again after 24 hours."
	),
	131050: _lt("This user has stopped receiving marketing messages."),
	131051: _lt("WhatsApp does not support this message type."),
	131052: _lt("The media the user sent could not be downloaded. Ask them to send it again."),
	131053: _lt("The media could not be uploaded. Check that WhatsApp supports its file type and size."),
	131057: _lt("The WhatsApp Business account is in maintenance mode. Try again in a few minutes."),
	133010: _lt("The phone number is not registered on the WhatsApp Business Platform."),
	# sending templates
	132000: _lt("The number of variable values does not match the template."),
	132001: _lt("The template does not exist in this language, or is not approved yet."),
	132005: _lt("The template text is too long once its variables are filled in."),
	132007: _lt("The template content violates a WhatsApp policy."),
	132012: _lt("A variable value is not in the format the template expects."),
	132015: _lt("The template is paused for low quality. Edit it and send it for review again."),
	132016: _lt("The template was paused too often and is disabled. Create a new template."),
	# creating templates (error_subcode)
	2388019: _lt(
		"The account reached its limit of 250 templates. Delete unused templates in WhatsApp Manager."
	),
	2388039: _lt("Meta is still reviewing this template, or it was edited too often today. Try again later."),
	2388040: _lt("A part of the template is longer than WhatsApp allows."),
	2388047: _lt("The template header is not in a format WhatsApp accepts."),
	2388072: _lt("The template message is not in a format WhatsApp accepts."),
	2388073: _lt("The template footer is not in a format WhatsApp accepts."),
	2388293: _lt(
		"The template has too many variables for its length. Use fewer variables or a longer message."
	),
	2388299: _lt("Variables cannot be at the start or end of the template. Add text before and after them."),
	2494100: _lt("The WhatsApp Business account is in maintenance mode. Try again in a few minutes."),
}


def with_docs_link(message: str) -> str:
	"""`message` followed by a link to Meta's WhatsApp documentation."""
	link = _("WhatsApp API documentation")
	return f'{message} · <a href="{DOCS_URL}" target="_blank" rel="noopener noreferrer">{link}</a>'


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
	except TypeError, ValueError:
		return None


def _permission_range(code: int | None) -> int | None:
	"""Meta reports permission errors anywhere in 200-299."""
	return 200 if code is not None and 200 <= code <= 299 else code
