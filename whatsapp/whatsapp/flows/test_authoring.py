# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
from itertools import count
from unittest.mock import patch

import frappe
import requests
from frappe.share import add_docshare
from frappe.tests import IntegrationTestCase

from whatsapp.whatsapp.doctype.wa_profile.wa_profile import get_or_create_profile
from whatsapp.whatsapp.flows.authoring import (
	FlowNameError,
	copy_flow,
	create_flow,
	delete_flow,
	save_flow,
)
from whatsapp.whatsapp.flows.builder_reads import get_flow_for_builder, get_flow_list
from whatsapp.whatsapp.flows.flow_json_fixtures import LEAD_QUALIFICATION, load
from whatsapp.whatsapp.flows.manage import publish_flow
from whatsapp.whatsapp.flows.meta_fixtures import (
	FlowMetaCase,
	flow_json_upload,
	make_account,
	validation_error,
)
from whatsapp.whatsapp.flows.template_fixtures import flow_button, template_doc

FLOW_IDS = count(8000)


class AuthoringCase(FlowMetaCase):
	def setUp(self):
		super().setUp()
		self.client.create_flow.side_effect = self.meta_creates
		self.client.update_flow_json.return_value = flow_json_upload()
		self.client.delete_flow.return_value = {"success": True}

	def meta_creates(self, name, categories, flow_json=None, clone_flow_id=None):
		flow_id = str(next(FLOW_IDS))
		source = self.meta.flow_json.get(clone_flow_id)
		self.meta.add(flow_id, name, flow_json=flow_json or source, status="DRAFT", categories=categories)
		return {"id": flow_id}

	def new_flow(self, flow_name: str = "Lead form", **kwargs) -> str:
		return create_flow(self.account, flow_name, ["LEAD_GENERATION"], **kwargs)

	def published_flow(self) -> str:
		name = self.new_flow("Published form")
		frappe.db.set_value("WA Flow", name, "status", "Published")
		return name

	def template_using(self, *buttons: dict) -> str:
		template = template_doc(
			self.account, list(buttons), template_name=f"_test_builder_{frappe.generate_hash(length=6)}"
		)
		template.flags.from_sync = True
		return template.insert().name


class IntegrationTestCreateFlow(AuthoringCase):
	def test_a_blank_flow_starts_on_meta_with_the_builders_one_screen_flow(self):
		name = self.new_flow()

		self.client.create_flow.assert_called_once_with(
			"Lead form", ["LEAD_GENERATION"], flow_json=json.dumps(load("builder", "blank"))
		)
		flow = frappe.get_doc("WA Flow", name)
		self.assertEqual(
			(flow.flow_name, flow.status, flow.whatsapp_account), ("Lead form", "Draft", self.account)
		)
		self.assertEqual(json.loads(flow.flow_json), load("builder", "blank"))

	def test_a_copy_clones_the_source_flow_on_meta(self):
		source = self.new_flow("Original")

		name = self.new_flow("Second", clone_from=source)

		self.client.create_flow.assert_called_with("Second", ["LEAD_GENERATION"], clone_flow_id=source)
		self.assertEqual(
			frappe.db.get_value("WA Flow", name, "flow_json"),
			frappe.db.get_value("WA Flow", source, "flow_json"),
		)

	def test_make_a_copy_clones_a_published_flow_with_its_categories(self):
		source = self.published_flow()

		name = copy_flow(source, "Published form (copy)")

		self.client.create_flow.assert_called_with(
			"Published form (copy)", ["LEAD_GENERATION"], clone_flow_id=source
		)
		self.assertEqual(frappe.db.get_value("WA Flow", name, "status"), "Draft")

	def test_a_name_already_used_in_the_business_is_refused_before_meta_is_called(self):
		self.new_flow("Lead form")
		other_number = make_account(
			business_id=frappe.db.get_value("WA Account", self.account, "business_id")
		)

		with self.assertRaises(FlowNameError):
			create_flow(other_number, "Lead form", ["SURVEY"])

		self.assertEqual(self.client.create_flow.call_count, 1)

	def test_an_unknown_category_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "MARKETING"):
			create_flow(self.account, "Lead form", ["MARKETING"])

		self.client.create_flow.assert_not_called()

	def test_a_meta_error_that_names_the_flow_name_is_raised_on_that_field(self):
		self.client.create_flow.side_effect = requests.HTTPError("Flow name is already used by another Flow")

		with self.assertRaisesRegex(FlowNameError, "already used by another Flow"):
			self.new_flow()

	def test_any_other_meta_error_is_shown_readably_and_nothing_is_stored(self):
		self.client.create_flow.side_effect = requests.HTTPError("Access token expired")

		with self.assertRaisesRegex(
			frappe.ValidationError, "Could not create the Flow: Access token expired"
		):
			self.new_flow()

		self.assertFalse(frappe.db.exists("WA Flow", {"whatsapp_account": self.account}))


class IntegrationTestSaveFlow(AuthoringCase):
	def setUp(self):
		super().setUp()
		self.name = self.new_flow()
		self.opened = get_flow_for_builder(self.name)

	def test_a_save_uploads_the_json_and_returns_meta_validation_errors_as_a_result(self):
		error = validation_error("Missing required property 'children'", path="screens[0].layout")
		self.client.update_flow_json.return_value = flow_json_upload(error)
		flow_json = json.dumps(LEAD_QUALIFICATION)

		saved = save_flow(self.name, flow_json, self.opened["modified"])

		self.client.update_flow_json.assert_called_once_with(self.name, flow_json)
		self.assertEqual(saved["validation_errors"], [error])
		self.assertEqual(saved["status"], "Draft")
		reopened = get_flow_for_builder(self.name)
		self.assertEqual(reopened["flow_json"], flow_json)
		self.assertEqual(reopened["validation_errors"], [error])
		self.assertEqual(reopened["modified"], saved["modified"])

	def test_the_returned_modified_allows_the_next_save(self):
		first = save_flow(self.name, json.dumps(LEAD_QUALIFICATION), self.opened["modified"])

		save_flow(self.name, json.dumps(load("builder", "feedback")), first["modified"])

		self.assertEqual(self.client.update_flow_json.call_count, 2)

	def test_a_save_from_a_stale_copy_is_refused_and_changes_nothing(self):
		save_flow(self.name, json.dumps(LEAD_QUALIFICATION), self.opened["modified"])

		with self.assertRaises(frappe.TimestampMismatchError):
			save_flow(self.name, json.dumps(load("builder", "feedback")), self.opened["modified"])

		self.assertEqual(self.client.update_flow_json.call_count, 1)
		self.assertEqual(
			json.loads(frappe.db.get_value("WA Flow", self.name, "flow_json")), LEAD_QUALIFICATION
		)

	def test_only_a_draft_can_be_saved(self):
		frappe.db.set_value("WA Flow", self.name, "status", "Published", update_modified=False)

		with self.assertRaisesRegex(frappe.ValidationError, "Only a Draft Flow"):
			save_flow(self.name, json.dumps(LEAD_QUALIFICATION), self.opened["modified"])

		self.client.update_flow_json.assert_not_called()

	def test_a_meta_failure_keeps_the_stored_json(self):
		self.client.update_flow_json.side_effect = requests.HTTPError("Meta is down")

		with self.assertRaisesRegex(frappe.ValidationError, "Meta is down"):
			save_flow(self.name, json.dumps(LEAD_QUALIFICATION), self.opened["modified"])

		self.assertEqual(
			json.loads(frappe.db.get_value("WA Flow", self.name, "flow_json")), load("builder", "blank")
		)

	def test_publish_returns_the_state_the_builder_shows_next(self):
		self.client.publish_flow.side_effect = lambda flow_id: self.meta.flows[flow_id].update(
			status="PUBLISHED"
		)

		published = publish_flow(self.name)

		self.assertEqual(published["status"], "Published")
		self.assertEqual(published["modified"], get_flow_for_builder(self.name)["modified"])


class IntegrationTestDeleteFlow(AuthoringCase):
	def test_an_unused_draft_is_deleted_on_meta_then_here(self):
		name = self.new_flow()

		delete_flow(name)

		self.client.delete_flow.assert_called_once_with(name)
		self.assertFalse(frappe.db.exists("WA Flow", name))

	def test_a_flow_used_by_templates_is_kept_and_the_templates_are_named(self):
		name = self.new_flow()
		self.template_using(flow_button(name))
		label = frappe.db.get_value("WA Template", {"whatsapp_account": self.account}, "template_label")

		with self.assertRaisesRegex(frappe.ValidationError, label):
			delete_flow(name)

		self.client.delete_flow.assert_not_called()
		self.assertTrue(frappe.db.exists("WA Flow", name))

	def test_a_flow_with_messages_is_kept(self):
		name = self.new_flow()
		frappe.get_doc(
			doctype="WA Message",
			direction="Incoming",
			to=get_or_create_profile("+15550001111", self.account),
			whatsapp_account=self.account,
			message="Form submitted",
			flow=name,
		).insert(ignore_permissions=True)

		with self.assertRaisesRegex(frappe.ValidationError, "messages"):
			delete_flow(name)

		self.client.delete_flow.assert_not_called()
		self.assertTrue(frappe.db.exists("WA Flow", name))

	def test_a_user_who_can_write_but_not_delete_flows_cannot_delete_one(self):
		name = self.new_flow()
		writer = _desk_user("flow.writer@example.com")
		add_docshare("WA Flow", name, writer, read=1, write=1, flags={"ignore_share_permission": True})

		with self.set_user(writer), self.assertRaises(frappe.PermissionError):
			delete_flow(name)

		self.client.delete_flow.assert_not_called()

	def test_only_a_draft_can_be_deleted(self):
		name = self.published_flow()

		with self.assertRaisesRegex(frappe.ValidationError, "Only a Draft Flow"):
			delete_flow(name)

		self.client.delete_flow.assert_not_called()

	def test_a_meta_failure_keeps_the_flow(self):
		name = self.new_flow()
		self.client.delete_flow.side_effect = requests.HTTPError("Flow cannot be deleted")

		with self.assertRaisesRegex(frappe.ValidationError, "Flow cannot be deleted"):
			delete_flow(name)

		self.assertTrue(frappe.db.exists("WA Flow", name))


class IntegrationTestBuilderPermissions(AuthoringCase):
	def test_a_user_who_can_only_read_flows_can_open_them_but_change_nothing(self):
		"""As CRM's sales roles: read on WA Flow and WA Account, nothing more."""
		name = self.new_flow()
		reader = _desk_user("flow.reader@example.com")
		for doctype, docname in (("WA Flow", name), ("WA Account", self.account)):
			add_docshare(doctype, docname, reader, read=1, flags={"ignore_share_permission": True})
		modified = get_flow_for_builder(name)["modified"]

		with self.set_user(reader):
			self.assertEqual(get_flow_for_builder(name)["name"], name)
			self.assertIn(name, [row["name"] for row in get_flow_list(self.account)])
			refused = {
				"create": lambda: self.new_flow("Mine"),
				"copy": lambda: copy_flow(name, "Copy"),
				"save": lambda: save_flow(name, json.dumps(LEAD_QUALIFICATION), modified),
				"publish": lambda: publish_flow(name),
				"delete": lambda: delete_flow(name),
			}
			for action, call in refused.items():
				with self.subTest(action=action), self.assertRaises(frappe.PermissionError):
					call()

		self.assertEqual(self.client.create_flow.call_count, 1)
		self.client.update_flow_json.assert_not_called()
		self.client.delete_flow.assert_not_called()

	def test_a_user_without_read_cannot_open_a_flow(self):
		name = self.new_flow()

		with self.set_user(_desk_user("no.flows@example.com")), self.assertRaises(frappe.PermissionError):
			get_flow_for_builder(name)


class IntegrationTestFlowEndpointMethods(IntegrationTestCase):
	def test_endpoints_that_change_flows_or_send_them_accept_only_post(self):
		from whatsapp.whatsapp.api.messages import send_flow
		from whatsapp.whatsapp.flows import authoring, manage
		from whatsapp.whatsapp.flows.sync import sync_flows

		endpoints = (
			authoring.create_flow,
			authoring.copy_flow,
			authoring.save_flow,
			authoring.delete_flow,
			manage.publish_flow,
			manage.deprecate_flow,
			manage.refresh_flow,
			sync_flows,
			send_flow,
		)
		for endpoint in endpoints:
			with self.subTest(endpoint=endpoint.__name__):
				self.assertEqual(list(frappe.allowed_http_methods_for_whitelisted_func[endpoint]), ["POST"])


def _desk_user(email: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(doctype="User", email=email, first_name="Flow", roles=[{"role": "Desk User"}]).insert(
			ignore_permissions=True
		)
	return email
