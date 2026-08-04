# Copyright (c) 2026, pratham@frappe.io and Contributors
# See license.txt

"""Tests for the conversation API in `whatsapp.whatsapp.api.messages`.

Most of this logic used to live in `crm.api.whatsapp`; the suite there is the ancestor of
this one. Two contract changes are asserted here on purpose:

- `status` is Title Case and passes through the API untouched (CRM lowercased it).
- `from_name` and `reply_to_from` no longer exist on the wire — the consumer labels a
  message from its `direction` and a host-supplied sender name.
"""

import datetime
import json
import secrets
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from whatsapp.whatsapp.api.messages import (
	_resolve_attachment,
	_validate_template_for_reference,
	_validate_template_is_approved,
	get_messages,
	react_to_message,
	send_message,
	send_template,
)
from whatsapp.whatsapp.api.utils import (
	humanize_error_message,
	infer_content_type,
	mime_type_for_content_type,
	parse_template_parameters,
)
from whatsapp.whatsapp.doctype.whatsapp_profile.whatsapp_profile import get_or_create_profile


def _message_row(name: str, **overrides) -> dict:
	"""A `WhatsApp Message` row shaped exactly like `MESSAGE_FIELDS` returns it."""
	row = {
		"name": name,
		"direction": "Outgoing",
		"to": "_Test Profile",
		"from": "15550001111",
		"mime_type": None,
		"is_template": 0,
		"media_url": None,
		"whatsapp_template": None,
		"message_id": f"wamid.{name}",
		"context_message_id": None,
		"creation": "2026-01-01 00:00:00",
		"message": "",
		"status": "Sent",
		"reference_doctype": "ToDo",
		"reference_docname": "TODO-0001",
		"template_body_parameters": None,
		"template_header_parameters": None,
		"reaction": None,
		"error_message": None,
	}
	row.update(overrides)
	return row


def _template_doc(**overrides) -> frappe._dict:
	"""A stand-in for a cached `WhatsApp Template` document."""
	doc = {
		"template_name": "tpl",
		"message": "",
		"header_text": "",
		"footer": "",
		"buttons": [],
	}
	doc.update(overrides)
	return frappe._dict(doc)


class TestParseTemplateParameters(UnitTestCase):
	"""Template parameters are stored as a dict, a list or a bare scalar."""

	def test_dict_substitutes_named_placeholders(self):
		result = parse_template_parameters(
			"Hi {{first_name}}, your deal {{deal_name}} is ready",
			{"first_name": "John", "deal_name": "ACME-001"},
		)
		self.assertEqual(result, "Hi John, your deal ACME-001 is ready")

	def test_dict_handles_whitespace_inside_placeholders(self):
		self.assertEqual(parse_template_parameters("Hi {{ first_name }}", {"first_name": "John"}), "Hi John")

	def test_dict_with_numeric_string_keys_acts_positional(self):
		"""Synced positional templates store parameters as a dict keyed by '1', '2', …"""
		result = parse_template_parameters("Hi {{1}}, your code is {{2}}", {"1": "John", "2": "ABC"})
		self.assertEqual(result, "Hi John, your code is ABC")

	def test_dict_leaves_unknown_placeholders_intact(self):
		result = parse_template_parameters("Hi {{first_name}} {{unknown}}", {"first_name": "John"})
		self.assertEqual(result, "Hi John {{unknown}}")

	def test_dict_coerces_non_string_values(self):
		self.assertEqual(parse_template_parameters("Amount: {{amount}}", {"amount": 5000}), "Amount: 5000")

	def test_list_substitutes_by_index(self):
		self.assertEqual(
			parse_template_parameters("Hi {{1}}, code {{2}}", ["John", "ABC"]), "Hi John, code ABC"
		)

	def test_list_ignores_named_placeholders(self):
		self.assertEqual(parse_template_parameters("Hi {{first_name}}", ["John"]), "Hi {{first_name}}")

	def test_list_out_of_range_left_intact(self):
		self.assertEqual(parse_template_parameters("{{1}} {{3}}", ["John", "Doe"]), "John {{3}}")

	def test_list_coerces_non_string_values(self):
		self.assertEqual(parse_template_parameters("Amount: {{1}}", [5000]), "Amount: 5000")

	def test_scalar_substitutes_first_placeholder(self):
		"""Header storage keeps a single value because Meta's header takes one variable."""
		self.assertEqual(parse_template_parameters("Welcome {{first_name}}!", "John"), "Welcome John!")

	def test_scalar_only_replaces_first_when_multiple_placeholders(self):
		self.assertEqual(parse_template_parameters("{{a}} and {{b}}", "X"), "X and {{b}}")

	def test_scalar_int_value(self):
		self.assertEqual(parse_template_parameters("Count: {{n}}", 42), "Count: 42")

	def test_empty_string_returns_empty(self):
		self.assertEqual(parse_template_parameters("", {"x": "y"}), "")

	def test_none_string_returns_none(self):
		self.assertIsNone(parse_template_parameters(None, {"x": "y"}))

	def test_none_parameters_returns_string_unchanged(self):
		self.assertEqual(parse_template_parameters("Hi {{x}}", None), "Hi {{x}}")

	def test_no_placeholders_returns_string_unchanged(self):
		self.assertEqual(parse_template_parameters("No vars here", {"x": "y"}), "No vars here")


class TestHumanizeErrorMessage(UnitTestCase):
	def test_extracts_message_from_meta_send_response(self):
		raw = (
			'{"error":{"message":"(#131030) Recipient phone number not in allowed list",'
			'"code":131030,"type":"OAuthException","error_data":{"messaging_product":"whatsapp",'
			'"details":"Recipient phone number not in allowed list: Add recipient phone number '
			'to recipient list and try again."},"fbtrace_id":"AeALCYwKZ1csanln8U18Q9i"}}'
		)
		self.assertEqual(
			humanize_error_message(raw),
			"(#131030) Recipient phone number not in allowed list",
		)

	def test_extracts_message_from_webhook_errors_array(self):
		raw = '[{"code":131030,"title":"Undeliverable","message":"(#131030) Not allowed"}]'
		self.assertEqual(humanize_error_message(raw), "(#131030) Not allowed")

	def test_falls_back_to_error_user_msg(self):
		raw = '{"error":{"code":131030,"error_user_msg":"Add the number to your allowed list"}}'
		self.assertEqual(humanize_error_message(raw), "Add the number to your allowed list")

	def test_falls_back_to_title(self):
		self.assertEqual(humanize_error_message('[{"code":131030,"title":"Undeliverable"}]'), "Undeliverable")

	def test_empty_errors_array_returns_original(self):
		self.assertEqual(humanize_error_message("[]"), "[]")

	def test_plain_string_returned_unchanged(self):
		self.assertEqual(humanize_error_message("Code 131030: boom"), "Code 131030: boom")

	def test_none_returned_unchanged(self):
		self.assertIsNone(humanize_error_message(None))

	def test_unparseable_json_returned_unchanged(self):
		self.assertEqual(humanize_error_message("{not json"), "{not json")


class TestContentTypeInference(UnitTestCase):
	def test_image_prefix(self):
		self.assertEqual(infer_content_type("image/png"), "image")

	def test_audio_prefix(self):
		self.assertEqual(infer_content_type("audio/ogg"), "audio")

	def test_video_prefix(self):
		self.assertEqual(infer_content_type("video/mp4"), "video")

	def test_prefix_match_is_case_insensitive(self):
		self.assertEqual(infer_content_type("IMAGE/JPEG"), "image")

	def test_unknown_mime_type_is_a_document(self):
		self.assertEqual(infer_content_type("application/pdf"), "document")

	def test_empty_mime_type_is_text(self):
		self.assertEqual(infer_content_type(""), "text")
		self.assertEqual(infer_content_type(None), "text")

	def test_mime_type_for_content_type_inverts_inference(self):
		for content_type in ("image", "document", "audio", "video"):
			with self.subTest(content_type=content_type):
				mime = mime_type_for_content_type(content_type)
				self.assertTrue(mime)
				self.assertEqual(infer_content_type(mime), content_type)

	def test_mime_type_for_unknown_content_type_is_blank(self):
		self.assertEqual(mime_type_for_content_type("text"), "")
		self.assertEqual(mime_type_for_content_type("sticker"), "")


class TestGetMessagesReferenceGuard(UnitTestCase):
	"""`references` comes from the client, so it is the security boundary of the read."""

	def _permissive_doc(self, *args, **kwargs):
		doc = MagicMock()
		doc.has_permission.return_value = True
		return doc

	def test_empty_reference_list_returns_nothing(self):
		with patch("frappe.get_all") as get_all:
			self.assertEqual(get_messages("[]"), [])
		get_all.assert_not_called()

	def test_unparseable_references_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			get_messages("not json at all")

	def test_non_list_references_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			get_messages('{"reference_doctype": "ToDo"}')

	def test_malformed_pair_is_rejected(self):
		for bad in ('[["ToDo"]]', '[["ToDo", "TODO-0001", "extra"]]', '[["ToDo", ""]]', '["ToDo"]'):
			with self.subTest(references=bad), self.assertRaises(frappe.ValidationError):
				get_messages(bad)

	def test_unknown_doctype_is_rejected(self):
		with patch("frappe.db.exists", return_value=False):
			with self.assertRaises(frappe.DoesNotExistError):
				get_messages('[["Not A DocType", "X"]]')

	def test_missing_reference_document_is_rejected(self):
		def _exists(doctype, name=None, *args, **kwargs):
			return doctype == "DocType"

		with patch("frappe.db.exists", side_effect=_exists), patch("frappe.get_all") as get_all:
			with self.assertRaises(frappe.DoesNotExistError):
				get_messages('[["ToDo", "TODO-9999"]]')
		get_all.assert_not_called()

	def test_unreadable_reference_document_is_rejected(self):
		doc = MagicMock()
		doc.has_permission.return_value = False
		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_doc", return_value=doc),
			patch("frappe.get_all") as get_all,
		):
			with self.assertRaises(frappe.PermissionError):
				get_messages('[["ToDo", "TODO-0001"]]')
		get_all.assert_not_called()

	def test_every_reference_is_checked_not_just_the_first(self):
		"""A permitted first reference must not smuggle an unpermitted second one through."""

		def _get_doc(doctype, name=None, *args, **kwargs):
			doc = MagicMock()
			doc.has_permission.return_value = name != "TODO-0002"
			return doc

		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_doc", side_effect=_get_doc),
			patch("frappe.get_all") as get_all,
		):
			with self.assertRaises(frappe.PermissionError):
				get_messages('[["ToDo", "TODO-0001"], ["ToDo", "TODO-0002"]]')
		get_all.assert_not_called()

	def test_duplicate_references_are_read_once(self):
		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_doc", side_effect=self._permissive_doc),
			patch("frappe.get_all", return_value=[]) as get_all,
		):
			get_messages('[["ToDo", "TODO-0001"], ["ToDo", "TODO-0001"]]')
		self.assertEqual(get_all.call_count, 1)


class TestGetMessages(UnitTestCase):
	"""Shape of the wire model returned to a conversation view."""

	def _run(self, rows, references=None, templates=None, files=None):
		references = references if references is not None else [["ToDo", "TODO-0001"]]
		templates = templates or {}
		files = files or []

		def _exists(doctype, name=None, *args, **kwargs):
			if doctype == "WhatsApp Template":
				return name in templates
			return True

		def _get_all(doctype, **kwargs):
			if doctype == "File":
				return [frappe._dict(f) for f in files]
			filters = kwargs.get("filters") or {}
			return [
				frappe._dict(row)
				for row in rows
				if row["reference_doctype"] == filters.get("reference_doctype")
				and row["reference_docname"] == filters.get("reference_docname")
			]

		def _get_doc(doctype, name=None, *args, **kwargs):
			doc = MagicMock()
			doc.has_permission.return_value = True
			return doc

		with (
			patch("frappe.db.exists", side_effect=_exists),
			patch("frappe.get_all", side_effect=_get_all),
			patch("frappe.get_doc", side_effect=_get_doc),
			patch("frappe.get_cached_doc", side_effect=lambda doctype, name: templates[name]),
		):
			return get_messages(json.dumps(references))

	def _by_name(self, messages) -> dict:
		return {m["name"]: m for m in messages}

	# --- multiple references ---------------------------------------------------------

	def test_multiple_references_merge_into_one_result_set(self):
		"""This is what replaced CRM's hard-coded Deal -> Lead union."""
		rows = [
			_message_row("m1", reference_docname="TODO-0001", message="on the deal"),
			_message_row("m2", reference_docname="TODO-0002", message="on the lead"),
		]
		messages = self._run(rows, references=[["ToDo", "TODO-0001"], ["ToDo", "TODO-0002"]])
		self.assertEqual(sorted(m["name"] for m in messages), ["m1", "m2"])

	def test_messages_of_an_unlisted_reference_are_not_returned(self):
		rows = [
			_message_row("m1", reference_docname="TODO-0001"),
			_message_row("m2", reference_docname="TODO-0002"),
		]
		messages = self._run(rows, references=[["ToDo", "TODO-0001"]])
		self.assertEqual([m["name"] for m in messages], ["m1"])

	# --- reaction folding ------------------------------------------------------------

	def test_reaction_rows_are_removed_and_folded_onto_their_target(self):
		rows = [
			_message_row("m1", message_id="wamid.1", creation="2026-01-01 00:00:01"),
			_message_row(
				"r1",
				direction="Incoming",
				reaction="👍",
				message="👍",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
			_message_row(
				"r2",
				direction="Outgoing",
				reaction="❤️",
				message="❤️",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:03",
			),
		]
		messages = self._run(rows)

		self.assertEqual([m["name"] for m in messages], ["m1"])
		self.assertEqual(
			sorted(messages[0]["reactions"], key=lambda r: r["direction"]),
			[{"emoji": "👍", "direction": "Incoming"}, {"emoji": "❤️", "direction": "Outgoing"}],
		)

	def test_later_reaction_from_the_same_direction_replaces_the_earlier_one(self):
		rows = [
			_message_row("m1", message_id="wamid.1", creation="2026-01-01 00:00:01"),
			_message_row(
				"r1",
				direction="Incoming",
				reaction="👍",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
			_message_row(
				"r2",
				direction="Incoming",
				reaction="😂",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:09",
			),
		]
		messages = self._run(rows)
		self.assertEqual(messages[0]["reactions"], [{"emoji": "😂", "direction": "Incoming"}])

	def test_message_without_reactions_gets_an_empty_list(self):
		messages = self._run([_message_row("m1")])
		self.assertEqual(messages[0]["reactions"], [])

	# --- reaction removal ------------------------------------------------------------
	#
	# Retracting a reaction arrives as a reaction row with an *empty* emoji (Meta omits
	# the `emoji` key; `webhook._create_incoming_message` stores ""). A non-reaction
	# message stores NULL, so "" vs None is what tells the two apart.

	def test_a_reaction_removal_retracts_the_reaction_it_points_at(self):
		rows = [
			_message_row("m1", message_id="wamid.1", creation="2026-01-01 00:00:01"),
			_message_row(
				"r1",
				direction="Incoming",
				reaction="👍",
				message="👍",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
			_message_row(
				"r2",
				direction="Incoming",
				reaction="",
				message="",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:03",
			),
		]
		self.assertEqual(self._run(rows)[0]["reactions"], [])

	def test_a_reaction_removal_is_not_rendered_as_a_blank_message(self):
		"""The empty emoji is falsy, so an unfixed gate leaves the row in as an empty bubble."""
		rows = [
			_message_row("m1", message_id="wamid.1", creation="2026-01-01 00:00:01"),
			_message_row(
				"r1",
				direction="Incoming",
				reaction="",
				message="",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
		]
		self.assertEqual([m["name"] for m in self._run(rows)], ["m1"])

	def test_a_removal_only_retracts_its_own_direction(self):
		rows = [
			_message_row("m1", message_id="wamid.1", creation="2026-01-01 00:00:01"),
			_message_row(
				"r1",
				direction="Incoming",
				reaction="👍",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
			_message_row(
				"r2",
				direction="Outgoing",
				reaction="❤️",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:03",
			),
			_message_row(
				"r3",
				direction="Incoming",
				reaction="",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:04",
			),
		]
		self.assertEqual(self._run(rows)[0]["reactions"], [{"emoji": "❤️", "direction": "Outgoing"}])

	def test_reacting_again_after_a_removal_restores_a_reaction(self):
		rows = [
			_message_row("m1", message_id="wamid.1", creation="2026-01-01 00:00:01"),
			_message_row(
				"r1",
				direction="Incoming",
				reaction="👍",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
			_message_row(
				"r2",
				direction="Incoming",
				reaction="",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:03",
			),
			_message_row(
				"r3",
				direction="Incoming",
				reaction="😂",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:04",
			),
		]
		self.assertEqual(self._run(rows)[0]["reactions"], [{"emoji": "😂", "direction": "Incoming"}])

	def test_a_removal_for_an_unknown_target_affects_nothing(self):
		rows = [
			_message_row("m1", message_id="wamid.1", creation="2026-01-01 00:00:01"),
			_message_row(
				"r1",
				direction="Incoming",
				reaction="👍",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
			_message_row(
				"r2",
				direction="Incoming",
				reaction="",
				context_message_id="wamid.elsewhere",
				creation="2026-01-01 00:00:03",
			),
		]
		self.assertEqual(self._run(rows)[0]["reactions"], [{"emoji": "👍", "direction": "Incoming"}])

	def test_an_empty_bodied_reply_is_not_mistaken_for_a_reaction_removal(self):
		"""A reply stores NULL in `reaction`; only a real removal row stores an empty string."""
		rows = [
			_message_row("m1", message_id="wamid.1", message="ping", creation="2026-01-01 00:00:01"),
			_message_row(
				"m2",
				message_id="wamid.2",
				message="",
				media_url="/files/pic.png",
				reaction=None,
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
		]
		self.assertEqual([m["name"] for m in self._run(rows)], ["m1", "m2"])

	# --- conversation ordering -------------------------------------------------------

	def test_messages_are_ordered_oldest_first(self):
		rows = [
			_message_row("m3", creation="2026-01-01 00:00:03"),
			_message_row("m1", creation="2026-01-01 00:00:01"),
			_message_row("m2", creation="2026-01-01 00:00:02"),
		]
		self.assertEqual([m["name"] for m in self._run(rows)], ["m1", "m2", "m3"])

	def test_ordering_is_asked_of_the_query_not_left_to_the_default(self):
		"""Without an explicit order_by the read falls back to `modified desc`."""
		captured = []

		def _get_all(doctype, **kwargs):
			captured.append(kwargs.get("order_by"))
			return []

		def _get_doc(doctype, name=None, *args, **kwargs):
			doc = MagicMock()
			doc.has_permission.return_value = True
			return doc

		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_all", side_effect=_get_all),
			patch("frappe.get_doc", side_effect=_get_doc),
		):
			get_messages('[["ToDo", "TODO-0001"]]')

		self.assertEqual(captured, ["creation asc, name asc"])

	def test_a_null_creation_does_not_break_ordering(self):
		"""`creation` is a datetime, so a null must not be sorted as an empty string."""
		rows = [
			_message_row("m2", creation=datetime.datetime(2026, 1, 1, 0, 0, 2)),
			_message_row("m0", creation=None),
			_message_row("m1", creation=datetime.datetime(2026, 1, 1, 0, 0, 1)),
		]
		self.assertEqual([m["name"] for m in self._run(rows)], ["m0", "m1", "m2"])

	def test_same_second_messages_are_ordered_deterministically(self):
		"""References are read one query at a time, so concatenation order must not decide."""
		stamp = datetime.datetime(2026, 1, 1, 0, 0, 1)
		rows = [
			_message_row("m1", reference_docname="TODO-0001", creation=stamp),
			_message_row("m2", reference_docname="TODO-0002", creation=stamp),
		]
		for references in (
			[["ToDo", "TODO-0001"], ["ToDo", "TODO-0002"]],
			[["ToDo", "TODO-0002"], ["ToDo", "TODO-0001"]],
		):
			with self.subTest(references=references):
				messages = self._run(rows, references=references)
				self.assertEqual([m["name"] for m in messages], ["m1", "m2"])

	def test_a_reply_is_not_mistaken_for_a_reaction(self):
		"""Replies also carry `context_message_id`; only a `reaction` value folds."""
		rows = [
			_message_row("m1", message_id="wamid.1", message="ping", creation="2026-01-01 00:00:01"),
			_message_row(
				"m2",
				message_id="wamid.2",
				message="pong",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
		]
		messages = self._run(rows)
		self.assertEqual(sorted(m["name"] for m in messages), ["m1", "m2"])

	# --- contract: removed fields ----------------------------------------------------

	def test_no_from_name_and_no_reply_to_from_anywhere(self):
		"""R6: sender labelling is presentation and is supplied by the host, not the API."""
		templates = {"tpl_a": _template_doc(template_name="tpl_a", message="Hello {{name}}")}
		rows = [
			_message_row("m1", message_id="wamid.1", message="ping", creation="2026-01-01 00:00:01"),
			_message_row(
				"m2",
				message_id="wamid.2",
				message="pong",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
			_message_row(
				"m3",
				message_id="wamid.3",
				is_template=1,
				whatsapp_template="tpl_a",
				template_body_parameters='{"name": "John"}',
				creation="2026-01-01 00:00:03",
			),
		]
		messages = self._run(rows, templates=templates)

		self.assertEqual(len(messages), 3)
		for message in messages:
			self.assertNotIn("from_name", message)
			self.assertNotIn("reply_to_from", message)

	def test_reactions_carry_no_from_name(self):
		rows = [
			_message_row("m1", message_id="wamid.1", creation="2026-01-01 00:00:01"),
			_message_row(
				"r1",
				direction="Incoming",
				reaction="👍",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
		]
		messages = self._run(rows)
		self.assertEqual(set(messages[0]["reactions"][0]), {"emoji", "direction"})

	# --- contract: native field names ------------------------------------------------

	def test_native_field_names_survive_untouched(self):
		"""The DocType's own field names go out on the wire — no CRM dialect rename."""
		rows = [
			_message_row(
				"m1",
				direction="Incoming",
				media_url="/files/pic.png",
				mime_type="image/png",
				whatsapp_template="tpl_a",
				context_message_id="wamid.0",
				is_template=0,
			)
		]
		message = self._run(rows)[0]

		self.assertEqual(message["direction"], "Incoming")
		self.assertEqual(message["media_url"], "/files/pic.png")
		self.assertEqual(message["whatsapp_template"], "tpl_a")
		self.assertEqual(message["context_message_id"], "wamid.0")
		self.assertEqual(message["reference_docname"], "TODO-0001")
		self.assertEqual(message["is_template"], 0)
		# CRM popped mime_type in favour of a derived `content_type`; the app keeps it and
		# lets the consumer derive the render kind.
		self.assertEqual(message["mime_type"], "image/png")

		for legacy in ("type", "attach", "template_parameters", "reference_name", "message_type"):
			self.assertNotIn(legacy, message)

	def test_title_case_status_passes_through_untouched(self):
		"""CRM lowercased status at the API boundary; the app stops doing that."""
		for status in ("Sent", "Delivered", "Read", "Failed", "Pending"):
			with self.subTest(status=status):
				message = self._run([_message_row("m1", status=status)])[0]
				self.assertEqual(message["status"], status)

	def test_error_message_is_humanized(self):
		raw = '{"error":{"message":"(#131030) Recipient phone number not in allowed list"}}'
		message = self._run([_message_row("m1", status="Failed", error_message=raw)])[0]
		self.assertEqual(message["error_message"], "(#131030) Recipient phone number not in allowed list")

	# --- reply resolution ------------------------------------------------------------

	def test_reply_resolution_sets_reply_keys(self):
		rows = [
			_message_row("m1", message_id="wamid.1", message="ping", creation="2026-01-01 00:00:01"),
			_message_row(
				"m2",
				direction="Incoming",
				message_id="wamid.2",
				message="pong",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
		]
		reply = self._by_name(self._run(rows))["m2"]

		self.assertEqual(reply["reply_message"], "ping")
		self.assertEqual(reply["reply_to"], "m1")
		self.assertEqual(reply["reply_to_direction"], "Outgoing")

	def test_reply_to_a_template_quotes_the_rendered_body(self):
		templates = {"tpl_a": _template_doc(template_name="tpl_a", message="Hello {{name}}")}
		rows = [
			_message_row(
				"m1",
				message_id="wamid.1",
				message="Template message",
				is_template=1,
				whatsapp_template="tpl_a",
				template_body_parameters='{"name": "John"}',
				creation="2026-01-01 00:00:01",
			),
			_message_row(
				"m2",
				message_id="wamid.2",
				message="pong",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
		]
		self.assertEqual(
			self._by_name(self._run(rows, templates=templates))["m2"]["reply_message"], "Hello John"
		)

	def test_reply_does_not_overwrite_the_replying_messages_own_header_and_footer(self):
		"""Regression: CRM copied the quoted message's header/footer onto the reply."""
		templates = {
			"tpl_a": _template_doc(
				template_name="tpl_a",
				message="Body A",
				header_text="Header A",
				footer="Footer A",
			),
			"tpl_b": _template_doc(
				template_name="tpl_b",
				message="Body B",
				header_text="Header B",
				footer="Footer B",
			),
		}
		rows = [
			_message_row(
				"m1",
				message_id="wamid.1",
				is_template=1,
				whatsapp_template="tpl_a",
				creation="2026-01-01 00:00:01",
			),
			_message_row(
				"m2",
				message_id="wamid.2",
				is_template=1,
				whatsapp_template="tpl_b",
				context_message_id="wamid.1",
				creation="2026-01-01 00:00:02",
			),
		]
		reply = self._by_name(self._run(rows, templates=templates))["m2"]

		self.assertEqual(reply["reply_message"], "Body A")
		self.assertEqual(reply["header"], "Header B")
		self.assertEqual(reply["footer"], "Footer B")
		self.assertEqual(reply["template"], "Body B")

	def test_unresolvable_reply_context_leaves_reply_keys_unset(self):
		"""A quoted message outside the fetched scope must not invent an empty quote."""
		rows = [_message_row("m1", message_id="wamid.1", context_message_id="wamid.elsewhere")]
		message = self._run(rows)[0]
		for key in ("reply_message", "reply_to", "reply_to_direction"):
			self.assertNotIn(key, message)

	# --- template rendering ----------------------------------------------------------

	def test_template_rendering_substitutes_body_header_and_attaches_buttons(self):
		templates = {
			"tpl_a": _template_doc(
				template_name="order_update",
				message="Hi {{name}}, order {{order_id}} shipped",
				header_text="Update for {{name}}",
				footer="Team Frappe",
				buttons=[
					frappe._dict(
						button_type="URL",
						button_text="Track",
						url="https://example.com",
						phone_number="",
					),
					frappe._dict(
						button_type="PHONE_NUMBER",
						button_text="Call us",
						url="",
						phone_number="+15551230000",
					),
				],
			)
		}
		rows = [
			_message_row(
				"m1",
				is_template=1,
				whatsapp_template="tpl_a",
				template_body_parameters='{"name": "John", "order_id": "A-1"}',
				template_header_parameters='"John"',
			)
		]
		message = self._run(rows, templates=templates)[0]

		self.assertEqual(message["template_name"], "order_update")
		self.assertEqual(message["template"], "Hi John, order A-1 shipped")
		self.assertEqual(message["header"], "Update for John")
		self.assertEqual(message["footer"], "Team Frappe")
		self.assertEqual(
			message["buttons"],
			[
				{
					"button_type": "URL",
					"button_text": "Track",
					"url": "https://example.com",
					"phone_number": "",
				},
				{
					"button_type": "PHONE_NUMBER",
					"button_text": "Call us",
					"url": "",
					"phone_number": "+15551230000",
				},
			],
		)

	def test_template_with_no_stored_parameters_keeps_placeholders(self):
		templates = {"tpl_a": _template_doc(template_name="tpl_a", message="Hi {{name}}")}
		rows = [_message_row("m1", is_template=1, whatsapp_template="tpl_a")]
		self.assertEqual(self._run(rows, templates=templates)[0]["template"], "Hi {{name}}")

	def test_malformed_stored_parameters_do_not_break_the_fetch(self):
		templates = {"tpl_a": _template_doc(template_name="tpl_a", message="Hi {{name}}")}
		rows = [
			_message_row(
				"m1",
				is_template=1,
				whatsapp_template="tpl_a",
				template_body_parameters="{not json",
			)
		]
		self.assertEqual(self._run(rows, templates=templates)[0]["template"], "Hi {{name}}")

	def test_deleted_template_is_skipped_not_fatal(self):
		rows = [_message_row("m1", is_template=1, whatsapp_template="gone")]
		message = self._run(rows, templates={})[0]
		self.assertNotIn("template", message)

	def test_non_template_message_is_not_rendered(self):
		templates = {"tpl_a": _template_doc(template_name="tpl_a", message="Hi {{name}}")}
		rows = [_message_row("m1", is_template=0, whatsapp_template="tpl_a", message="plain text")]
		message = self._run(rows, templates=templates)[0]
		self.assertNotIn("template", message)
		self.assertEqual(message["message"], "plain text")

	# --- file join -------------------------------------------------------------------

	def test_file_details_are_joined_onto_media_messages(self):
		rows = [
			_message_row("m1", media_url="/files/report.pdf", mime_type="application/pdf"),
			_message_row("m2", message="no media"),
		]
		files = [{"file_url": "/files/report.pdf", "file_name": "report.pdf", "file_size": 2048}]
		messages = self._by_name(self._run(rows, files=files))

		self.assertEqual(messages["m1"]["file_name"], "report.pdf")
		self.assertEqual(messages["m1"]["file_size"], 2048)
		self.assertNotIn("file_name", messages["m2"])

	def test_file_lookup_is_skipped_when_no_message_has_media(self):
		def _get_all(doctype, **kwargs):
			if doctype == "File":
				raise AssertionError("File must not be queried when nothing has media_url")
			return [frappe._dict(_message_row("m1"))]

		def _get_doc(doctype, name=None, *args, **kwargs):
			doc = MagicMock()
			doc.has_permission.return_value = True
			return doc

		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_all", side_effect=_get_all),
			patch("frappe.get_doc", side_effect=_get_doc),
		):
			get_messages('[["ToDo", "TODO-0001"]]')

	def test_missing_file_record_leaves_media_message_intact(self):
		rows = [_message_row("m1", media_url="/files/gone.png")]
		message = self._run(rows, files=[])[0]
		self.assertEqual(message["media_url"], "/files/gone.png")
		self.assertNotIn("file_name", message)


class TestSendMessageValidation(UnitTestCase):
	def test_empty_message_without_attachment_is_rejected(self):
		"""Whitespace-only text and no attachment must not create or send anything."""
		with patch("frappe.new_doc") as new_doc:
			with self.assertRaises(frappe.ValidationError):
				send_message(to="+15551234567", message="   ")
		new_doc.assert_not_called()

	def test_unreadable_reference_document_is_rejected(self):
		doc = MagicMock()
		doc.has_permission.return_value = False
		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_doc", return_value=doc),
			patch("frappe.new_doc") as new_doc,
		):
			with self.assertRaises(frappe.PermissionError):
				send_message(
					to="+15551234567",
					message="hello",
					reference_doctype="ToDo",
					reference_docname="TODO-0001",
				)
		new_doc.assert_not_called()

	def test_attachment_matching_no_file_is_rejected(self):
		"""An unresolvable attachment used to submit a text message with an empty body."""
		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.db.get_value", return_value=None),
			patch("frappe.new_doc") as new_doc,
		):
			with self.assertRaises(frappe.DoesNotExistError):
				send_message(to="+15551234567", message="", attach="/files/gone.png")
		new_doc.assert_not_called()


class TestResolveAttachment(UnitTestCase):
	def test_resolves_a_file_url_to_its_docname(self):
		with patch("frappe.db.get_value", return_value="FILE-0001"):
			self.assertEqual(_resolve_attachment("/files/pic.png"), "FILE-0001")

	def test_colliding_file_urls_resolve_to_the_oldest_file(self):
		"""Copying an attachment creates a second File on the same URL; the match must be stable."""
		with patch("frappe.db.get_value", return_value="FILE-0001") as get_value:
			_resolve_attachment("/files/pic.png")

		self.assertEqual(get_value.call_args.kwargs["order_by"], "creation asc, name asc")

	def test_unknown_file_url_is_rejected(self):
		with patch("frappe.db.get_value", return_value=None):
			with self.assertRaises(frappe.DoesNotExistError):
				_resolve_attachment("/files/gone.png")


class TestValidateTemplateIsApproved(UnitTestCase):
	"""`get_sendable_templates` filters a picker to Approved, but the endpoint takes any name."""

	def test_approved_template_passes(self):
		with patch("frappe.db.get_value", return_value="Approved"):
			_validate_template_is_approved("tpl_a")

	def test_unapproved_statuses_are_rejected(self):
		for status in ("Pending", "Rejected", "Deleted"):
			with self.subTest(status=status), patch("frappe.db.get_value", return_value=status):
				with self.assertRaises(frappe.ValidationError) as ctx:
					_validate_template_is_approved("tpl_a")
				self.assertIn(status, str(ctx.exception))

	def test_missing_status_is_rejected(self):
		with patch("frappe.db.get_value", return_value=None):
			with self.assertRaises(frappe.ValidationError):
				_validate_template_is_approved("tpl_a")


class TestReactToMessagePermissions(UnitTestCase):
	def test_missing_message_is_rejected(self):
		with patch("frappe.db.exists", return_value=False):
			with self.assertRaises(frappe.DoesNotExistError):
				react_to_message("WA-MSG-0001", "👍")

	def test_unreadable_message_is_rejected(self):
		doc = MagicMock()
		doc.has_permission.return_value = False
		with patch("frappe.db.exists", return_value=True), patch("frappe.get_doc", return_value=doc):
			with self.assertRaises(frappe.PermissionError):
				react_to_message("WA-MSG-0001", "👍")

	def test_unreadable_reference_document_is_rejected(self):
		"""Reading the message is not enough — its reference document is checked too."""
		message_doc = MagicMock()
		message_doc.has_permission.return_value = True
		message_doc.reference_doctype = "ToDo"
		message_doc.reference_docname = "TODO-0001"

		reference_doc = MagicMock()
		reference_doc.has_permission.return_value = False

		def _get_doc(doctype, name=None, *args, **kwargs):
			return message_doc if doctype == "WhatsApp Message" else reference_doc

		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_doc", side_effect=_get_doc),
			patch("frappe.new_doc") as new_doc,
		):
			with self.assertRaises(frappe.PermissionError):
				react_to_message("WA-MSG-0001", "👍")
		new_doc.assert_not_called()


class TestSendTemplatePermissions(UnitTestCase):
	def test_unreadable_reference_document_is_rejected(self):
		doc = MagicMock()
		doc.has_permission.return_value = False
		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_doc", return_value=doc),
			patch("frappe.new_doc") as new_doc,
		):
			with self.assertRaises(frappe.PermissionError):
				send_template("tpl_a", "+15551234567", "ToDo", "TODO-0001")
		new_doc.assert_not_called()

	def test_unapproved_template_is_rejected_by_the_endpoint(self):
		"""The picker only offers Approved templates; the endpoint has to enforce it too."""
		reference = MagicMock()
		reference.has_permission.return_value = True
		template = MagicMock()
		template.get.side_effect = lambda key, default=None: {"template_variables": []}.get(key, default)

		with (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_doc", return_value=reference),
			patch("frappe.get_cached_doc", return_value=template),
			patch("frappe.db.get_value", return_value="Pending"),
			patch("frappe.new_doc") as new_doc,
		):
			with self.assertRaises(frappe.ValidationError) as ctx:
				send_template("tpl_a", "+15551234567", "ToDo", "TODO-0001")
			self.assertIn("Pending", str(ctx.exception))
		new_doc.assert_not_called()


class TestValidateTemplateForReference(UnitTestCase):
	def _patch_template(self, **fields):
		"""Stub `frappe.db.exists` + `frappe.get_cached_doc` for a WhatsApp Template."""
		template = MagicMock()
		template.get.side_effect = lambda key, default=None: fields.get(key, default)
		return (
			patch("frappe.db.exists", return_value=True),
			patch("frappe.get_cached_doc", return_value=template),
		)

	def test_raises_when_template_does_not_exist(self):
		with patch("frappe.db.exists", return_value=False):
			with self.assertRaises(frappe.DoesNotExistError):
				_validate_template_for_reference("missing_template", "ToDo")

	def test_passes_when_template_has_no_variables(self):
		exists, get_cached_doc = self._patch_template(template_variables=[], reference_doctype="")
		with exists, get_cached_doc:
			_validate_template_for_reference("plain_template", "ToDo")

	def test_passes_for_unbound_template_without_variables_sent_from_nowhere(self):
		exists, get_cached_doc = self._patch_template(template_variables=[], reference_doctype="")
		with exists, get_cached_doc:
			_validate_template_for_reference("plain_template", None)

	def test_raises_when_template_has_variables_but_no_reference_doctype(self):
		exists, get_cached_doc = self._patch_template(template_variables=[MagicMock()], reference_doctype="")
		with exists, get_cached_doc:
			with self.assertRaises(frappe.ValidationError) as ctx:
				_validate_template_for_reference("orphan_template", "ToDo")
			self.assertIn("not bound to a reference DocType", str(ctx.exception))

	def test_raises_when_template_doctype_mismatches(self):
		exists, get_cached_doc = self._patch_template(
			template_variables=[MagicMock()], reference_doctype="ToDo"
		)
		with exists, get_cached_doc:
			with self.assertRaises(frappe.ValidationError) as ctx:
				_validate_template_for_reference("todo_template", "Contact")
			self.assertIn("ToDo", str(ctx.exception))
			self.assertIn("Contact", str(ctx.exception))

	def test_passes_when_template_doctype_matches(self):
		exists, get_cached_doc = self._patch_template(
			template_variables=[MagicMock()], reference_doctype="ToDo"
		)
		with exists, get_cached_doc:
			_validate_template_for_reference("todo_template", "ToDo")

	def test_raises_when_a_variable_field_is_unmapped(self):
		"""A Template Variable row without a variable_field cannot resolve at send time."""
		unmapped = MagicMock()
		unmapped.variable_name = "first_name"
		unmapped.variable_field = ""
		exists, get_cached_doc = self._patch_template(template_variables=[unmapped], reference_doctype="ToDo")
		with exists, get_cached_doc:
			with self.assertRaises(frappe.ValidationError) as ctx:
				_validate_template_for_reference("todo_template", "ToDo")
			self.assertIn("first_name", str(ctx.exception))
			self.assertIn("Variable Field", str(ctx.exception))

	def test_lists_every_unmapped_variable(self):
		mapped = MagicMock()
		mapped.variable_name = "amount"
		mapped.variable_field = "amount"
		first = MagicMock()
		first.variable_name = "first_name"
		first.variable_field = ""
		last = MagicMock()
		last.variable_name = "last_name"
		last.variable_field = ""

		exists, get_cached_doc = self._patch_template(
			template_variables=[first, mapped, last], reference_doctype="ToDo"
		)
		with exists, get_cached_doc:
			with self.assertRaises(frappe.ValidationError) as ctx:
				_validate_template_for_reference("todo_template", "ToDo")
			message = str(ctx.exception)
			self.assertIn("first_name", message)
			self.assertIn("last_name", message)
			self.assertNotIn("amount", message)


class IntegrationTestSendMessage(IntegrationTestCase):
	"""Round trips that need a real `WhatsApp Message` document."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.account = self._make_account()
		settings = frappe.get_single("WhatsApp Settings")
		settings.default_account = self.account
		settings.save(ignore_permissions=True)
		self.todo = frappe.get_doc(doctype="ToDo", description="_Test WhatsApp reference").insert()
		self.phone = f"+1{secrets.randbelow(10**10):010d}"

	def _make_account(self) -> str:
		uid = frappe.generate_hash(length=6)
		return (
			frappe.get_doc(
				doctype="WhatsApp Account",
				account_name=f"_Test Msg Acc {uid}",
				status="Active",
				phone_id=f"phone_{uid}",
				business_id="test_biz",
				app_id="test_app",
				access_token="test_token",
			)
			.insert()
			.name
		)

	def _make_file(self):
		uid = frappe.generate_hash(length=6)
		return frappe.get_doc(
			doctype="File",
			file_name=f"pic_{uid}.png",
			is_private=0,
			content=b"png_bytes",
		).insert()

	def _make_draft_message(self, **overrides):
		"""An unsent outgoing message usable as a reply/reaction target."""
		profile = get_or_create_profile(self.phone, self.account, self.phone, self.phone)

		data = dict(
			doctype="WhatsApp Message",
			direction="Outgoing",
			whatsapp_account=self.account,
			to=profile,
			message="target",
			message_id="wamid.target",
			reference_doctype="ToDo",
			reference_docname=self.todo.name,
		)
		data.update(overrides)
		return frappe.get_doc(data).insert()

	# --- attachments -----------------------------------------------------------------

	def test_attachment_resolves_the_file_url_to_a_file_docname(self):
		"""The send path resolves `attach` as a File docname, so the URL must be mapped."""
		file_doc = self._make_file()
		with (
			patch(
				"whatsapp.whatsapp.api.whatsapp.WhatsApp.upload_media",
				return_value={"id": "media_999"},
			) as upload_media,
			patch(
				"whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message",
				return_value={"messages": [{"id": "wamid.sent"}]},
			) as send,
		):
			name = send_message(
				to=self.phone,
				message="",
				attach=file_doc.file_url,
				content_type="image",
				reference_doctype="ToDo",
				reference_docname=self.todo.name,
			)

		message = frappe.get_doc("WhatsApp Message", name)
		self.assertEqual(message.attach, file_doc.name)
		# The file URL must never leak into the text body.
		self.assertNotIn("/files/", message.message or "")
		self.assertEqual(message.media_url, file_doc.file_url)

		upload_media.assert_called_once()
		payload = send.call_args[0][0]
		self.assertEqual(payload["type"], "image")
		self.assertEqual(payload["image"]["id"], "media_999")

	def test_media_url_and_mime_type_are_stamped_for_display(self):
		"""`media_url`/`mime_type` are set before the send so the bubble renders at once."""
		file_doc = self._make_file()
		with patch("whatsapp.whatsapp.api.messages._submit"):
			name = send_message(
				to=self.phone,
				message="look at this",
				attach=file_doc.file_url,
				content_type="image",
				reference_doctype="ToDo",
				reference_docname=self.todo.name,
			)

		self.assertEqual(frappe.db.get_value("WhatsApp Message", name, "media_url"), file_doc.file_url)
		self.assertEqual(frappe.db.get_value("WhatsApp Message", name, "mime_type"), "image/jpeg")
		# The caption stays the caption; it is not replaced by the URL.
		self.assertEqual(frappe.db.get_value("WhatsApp Message", name, "message"), "look at this")

	def test_attachment_with_no_matching_file_sends_nothing(self):
		"""It used to fall through to an empty-bodied text message reaching Meta."""
		before = frappe.db.count("WhatsApp Message")
		with patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message") as send:
			with self.assertRaises(frappe.DoesNotExistError):
				send_message(
					to=self.phone,
					message="",
					attach="/files/not-a-real-file.png",
					content_type="image",
					reference_doctype="ToDo",
					reference_docname=self.todo.name,
				)

		send.assert_not_called()
		self.assertEqual(frappe.db.count("WhatsApp Message"), before)

	# --- replies ---------------------------------------------------------------------

	def test_reply_sets_context_message_id_from_the_referenced_message(self):
		target = self._make_draft_message(message_id="wamid.quoted")
		with patch("whatsapp.whatsapp.api.messages._submit"):
			name = send_message(
				to=self.phone,
				message="replying",
				reply_to=target.name,
				reference_doctype="ToDo",
				reference_docname=self.todo.name,
			)
		self.assertEqual(frappe.db.get_value("WhatsApp Message", name, "context_message_id"), "wamid.quoted")

	def test_reply_to_an_unknown_message_is_rejected(self):
		with self.assertRaises(frappe.DoesNotExistError):
			send_message(
				to=self.phone,
				message="replying",
				reply_to="WA-MSG-does-not-exist",
				reference_doctype="ToDo",
				reference_docname=self.todo.name,
			)

	def test_reply_to_an_unacknowledged_message_is_rejected(self):
		"""No `message_id` means no id to quote — the send used to silently drop the quote."""
		target = self._make_draft_message(message_id=None, status="Pending")
		with patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message") as send:
			with self.assertRaises(frappe.ValidationError) as ctx:
				send_message(
					to=self.phone,
					message="replying",
					reply_to=target.name,
					reference_doctype="ToDo",
					reference_docname=self.todo.name,
				)
		self.assertIn(target.name, str(ctx.exception))
		send.assert_not_called()

	# --- reactions -------------------------------------------------------------------

	def test_reaction_is_stored_as_its_own_message_pointing_at_the_target(self):
		target = self._make_draft_message(message_id="wamid.reactme")
		with patch("whatsapp.whatsapp.api.messages._submit"):
			name = react_to_message(target.name, "👍")

		reaction = frappe.get_doc("WhatsApp Message", name)
		self.assertEqual(reaction.reaction, "👍")
		self.assertEqual(reaction.context_message_id, "wamid.reactme")
		self.assertEqual(reaction.reference_doctype, "ToDo")
		self.assertEqual(reaction.reference_docname, self.todo.name)
		self.assertEqual(reaction.to, target.to)

	def test_reacting_to_an_unacknowledged_message_is_rejected(self):
		"""Without a `message_id` the payload builder falls through and sends the bare emoji as text."""
		target = self._make_draft_message(message_id=None, status="Pending")
		with patch("whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message") as send:
			with self.assertRaises(frappe.ValidationError) as ctx:
				react_to_message(target.name, "👍")

		self.assertIn(target.name, str(ctx.exception))
		send.assert_not_called()
		self.assertFalse(frappe.db.exists("WhatsApp Message", {"reaction": "👍"}))

	# --- send failure ----------------------------------------------------------------

	def test_failed_send_leaves_a_failed_row_instead_of_vanishing(self):
		"""CRM swallowed send errors with `except: pass`; the app records them."""
		from requests import HTTPError

		with patch(
			"whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message",
			side_effect=HTTPError("Meta rejected: number not on WhatsApp"),
		):
			name = send_message(
				to=self.phone,
				message="hello",
				reference_doctype="ToDo",
				reference_docname=self.todo.name,
			)

		self.assertTrue(name)
		message = frappe.get_doc("WhatsApp Message", name)
		self.assertEqual(message.status, "Failed")
		self.assertIn("Meta rejected", message.error_message or "")

		self.assertTrue(
			frappe.db.exists(
				"WhatsApp Log",
				{
					"level": "Error",
					"reference_doctype": "WhatsApp Message",
					"reference_docname": name,
				},
			)
		)

	def test_failed_send_does_not_also_raise_an_error_dialog(self):
		"""The Failed row is the single channel: no `_server_messages` may ride along with it."""
		from requests import HTTPError

		frappe.clear_messages()
		with patch(
			"whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message",
			side_effect=HTTPError("Meta rejected: number not on WhatsApp"),
		):
			name = send_message(
				to=self.phone,
				message="hello",
				reference_doctype="ToDo",
				reference_docname=self.todo.name,
			)

		self.assertEqual(frappe.get_message_log(), [])
		self.assertEqual(frappe.db.get_value("WhatsApp Message", name, "status"), "Failed")

	def test_clearing_the_failure_dialog_leaves_earlier_messages_alone(self):
		"""Only what the failed submit added is dropped, not an unrelated earlier msgprint."""
		from requests import HTTPError

		frappe.clear_messages()
		frappe.msgprint("earlier and unrelated")
		with patch(
			"whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message",
			side_effect=HTTPError("Meta rejected"),
		):
			send_message(
				to=self.phone,
				message="hello",
				reference_doctype="ToDo",
				reference_docname=self.todo.name,
			)

		log = frappe.get_message_log()
		self.assertEqual(len(log), 1)
		self.assertIn("earlier and unrelated", str(log[0]))
		frappe.clear_messages()

	def test_unexpected_submit_failure_is_recorded_by_submit_helper(self):
		"""Failures the send path does not classify still land as a Failed row + a log."""
		with patch(
			"whatsapp.whatsapp.doctype.whatsapp_message.whatsapp_message.WhatsAppMessage._send",
			side_effect=RuntimeError("boom"),
		):
			name = send_message(
				to=self.phone,
				message="hello",
				reference_doctype="ToDo",
				reference_docname=self.todo.name,
			)

		self.assertEqual(frappe.db.get_value("WhatsApp Message", name, "status"), "Failed")
		self.assertIn("boom", frappe.db.get_value("WhatsApp Message", name, "error_message") or "")
		self.assertTrue(
			frappe.db.exists(
				"WhatsApp Log",
				{
					"level": "Error",
					"reference_doctype": "WhatsApp Message",
					"reference_docname": name,
				},
			)
		)

	def test_failed_message_is_readable_back_through_get_messages(self):
		from requests import HTTPError

		raw_error = '{"error":{"message":"(#131030) Recipient phone number not in allowed list"}}'
		with patch(
			"whatsapp.whatsapp.api.whatsapp.WhatsApp.send_message",
			side_effect=HTTPError(raw_error),
		):
			name = send_message(
				to=self.phone,
				message="hello",
				reference_doctype="ToDo",
				reference_docname=self.todo.name,
			)

		messages = get_messages(json.dumps([["ToDo", self.todo.name]]))
		failed = next(m for m in messages if m["name"] == name)
		self.assertEqual(failed["status"], "Failed")
		self.assertEqual(failed["error_message"], "(#131030) Recipient phone number not in allowed list")
