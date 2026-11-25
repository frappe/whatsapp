# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from whatsapp.whatsapp.api.utils import log
from whatsapp.whatsapp.flows.manage import upload_flow_json
from whatsapp.whatsapp.flows.outline import FlowOutline


class WAFlow(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		business_id: DF.Data | None
		categories: DF.SmallText | None
		endpoint_uri: DF.Data | None
		flow_id: DF.Data
		flow_json: DF.Code | None
		flow_name: DF.Data | None
		json_version: DF.Data | None
		outline: DF.JSON | None
		preview_expires_at: DF.Datetime | None
		preview_url: DF.Data | None
		status: DF.Literal["Draft", "Published", "Throttled", "Blocked", "Deprecated"]
		validation_errors: DF.Code | None
		whatsapp_account: DF.Link
	# end: auto-generated types

	def before_save(self) -> None:
		if not self.has_value_changed("flow_json"):
			return
		if self._edited_by_user():
			upload_flow_json(self)
		self.outline = self._read_outline()

	def on_update(self) -> None:
		if self.flags.outline_error:
			self.log(
				"Warning", f"Flow {self.flow_name or self.name} has no outline: {self.flags.outline_error}"
			)

	def on_trash(self) -> None:
		frappe.db.delete("WA Log", {"reference_doctype": "WA Flow", "reference_docname": self.name})

	def log(self, level: str, message: str, **data) -> None:
		saved = not self.is_new()
		data.setdefault("account", self.whatsapp_account)
		log(
			level,
			"Flow",
			message,
			reference_doctype="WA Flow" if saved else None,
			reference_docname=self.name if saved else None,
			**data,
		)

	def get_outline(self) -> FlowOutline:
		return FlowOutline.from_dict(frappe.parse_json(self.outline))

	def _edited_by_user(self) -> bool:
		# Flows are created only by sync, so a new one is never uploaded.
		return not (self.is_new() or self.flags.from_sync)

	def _read_outline(self) -> dict:
		if self.flow_json:
			try:
				return FlowOutline.from_flow_json(self.flow_json).as_dict()
			except ValueError as e:
				# A draft Flow on Meta can hold invalid JSON, so the Flow is still saved.
				self.flags.outline_error = str(e)
		return FlowOutline(screens=[], entry_screens={}, answers=[], sensitive=[]).as_dict()
