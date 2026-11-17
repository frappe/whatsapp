# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json

from frappe.tests import UnitTestCase

from whatsapp.whatsapp.api.meta_errors import DOCS_URL, META_ERRORS, describe_meta_error, with_docs_link
from whatsapp.whatsapp.api.whatsapp import _extract_meta_error

TEMPLATE_REFUSAL = {
	"error": {
		"message": "Invalid parameter",
		"type": "OAuthException",
		"code": 100,
		"error_subcode": 2388293,
		"is_transient": False,
		"error_user_title": "Params Words Ratio Exceeds Limit",
		"error_user_msg": "This template has too many variables for its length. Reduce the number of variables or increase the message length.",
		"fbtrace_id": "AAmEIgePUsBvJlMhYccWF8E",
	}
}


class TestMetaErrors(UnitTestCase):
	def test_a_meta_response_body_becomes_its_readable_message(self):
		self.assertEqual(
			_extract_meta_error(json.dumps(TEMPLATE_REFUSAL)),
			TEMPLATE_REFUSAL["error"]["error_user_msg"],
		)

	def test_the_subcode_explains_a_generic_invalid_parameter(self):
		error = {"message": "Invalid parameter", "code": 100, "error_subcode": 2388299}
		self.assertEqual(describe_meta_error(error), str(META_ERRORS[2388299]))

	def test_a_known_code_replaces_metas_terse_message(self):
		error = {"message": "Error validating access token: Session has expired", "code": 190}
		self.assertEqual(describe_meta_error(error), str(META_ERRORS[190]))

	def test_any_code_in_the_permission_range_reads_as_a_permission_error(self):
		self.assertEqual(describe_meta_error({"code": 299}), str(META_ERRORS[200]))

	def test_an_unknown_code_keeps_metas_message(self):
		self.assertEqual(describe_meta_error({"code": 999999, "message": "Odd"}), "Odd")

	def test_a_body_that_is_not_a_meta_error_comes_back_unchanged(self):
		self.assertEqual(_extract_meta_error("<html>Bad Gateway</html>"), "<html>Bad Gateway</html>")
		self.assertEqual(_extract_meta_error('["not", "an", "object"]'), '["not", "an", "object"]')

	def test_a_shown_error_links_to_the_docs(self):
		shown = with_docs_link("Meta rejected the request")

		self.assertTrue(shown.startswith("Meta rejected the request · "))
		self.assertIn(f'href="{DOCS_URL}"', shown)
