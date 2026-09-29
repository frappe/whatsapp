from collections import defaultdict

import frappe

from whatsapp.whatsapp.doctype.wa_profile.wa_profile import normalize_phone


def execute():
	"""Profiles that normalize onto one number keep the one Meta created (it has a
	`wa_id`), or else the oldest; the other's messages and links move over."""
	profiles = frappe.get_all(
		"WA Profile",
		fields=["name", "phone_number", "whatsapp_account", "wa_id"],
		order_by="creation asc",
	)

	groups = defaultdict(list)
	for profile in profiles:
		normalized = _normalize_stored(profile.phone_number)
		if normalized:
			groups[(profile.whatsapp_account, normalized)].append(profile)

	for (_account, phone_number), duplicates in groups.items():
		survivor = next((profile for profile in duplicates if profile.wa_id), duplicates[0])
		losers = [profile.name for profile in duplicates if profile.name != survivor.name]
		if losers:
			_merge(losers, into=survivor.name, phone_number=phone_number)
		elif phone_number != survivor.phone_number:
			frappe.db.set_value(
				"WA Profile", survivor.name, "phone_number", phone_number, update_modified=False
			)


def _normalize_stored(phone_number: str | None) -> str:
	# A digits-only number was written by Meta's webhook or by the notification channel
	# stripping a plus, so it already carries its country code and must not be read as a
	# national number: Singapore's 6591234567 is also a valid Indian mobile.
	if phone_number and phone_number.strip().isdigit():
		phone_number = f"+{phone_number.strip()}"
	return normalize_phone(phone_number)


def _merge(losers: list[str], into: str, phone_number: str) -> None:
	frappe.db.set_value("WA Message", {"to": ("in", losers)}, "to", into, update_modified=False)
	loser_links = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "WA Profile", "parent": ("in", losers)},
		fields=["link_doctype", "link_name", "link_title"],
		order_by="parent, idx",
	)
	# deleted before the target is saved, or the target's unique-phone validation finds them
	for loser in losers:
		frappe.delete_doc("WA Profile", loser, ignore_permissions=True, force=True)

	target = frappe.get_doc("WA Profile", into)
	target.phone_number = phone_number
	existing = {(link.link_doctype, link.link_name) for link in target.links}
	for link in loser_links:
		if (link.link_doctype, link.link_name) not in existing:
			existing.add((link.link_doctype, link.link_name))
			target.append("links", link)
	target.save(ignore_permissions=True)
