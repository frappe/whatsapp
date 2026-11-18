# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from datetime import datetime

import frappe
from frappe.utils import convert_utc_to_system_timezone

from whatsapp.whatsapp.api.utils import log
from whatsapp.whatsapp.doctype.wa_template.wa_template import _get_whatsapp_client

FLOW_STATUSES = {
	"DRAFT": "Draft",
	"PUBLISHED": "Published",
	"THROTTLED": "Throttled",
	"BLOCKED": "Blocked",
	"DEPRECATED": "Deprecated",
}


@frappe.whitelist()
def sync_flows(account_name: str) -> dict:
	"""Return counts of created, updated and removed Flows."""
	frappe.has_permission("WA Flow", "write", throw=True)
	frappe.has_permission("WA Account", "read", doc=account_name, throw=True)
	return FlowSync(account_name).sync_account()


def sync_flow(account_name: str, flow_id: str) -> None:
	FlowSync(account_name).upsert(flow_id)


def sync_active_accounts() -> None:
	for account_name in frappe.get_all("WA Account", filters={"status": "Active"}, pluck="name"):
		frappe.db.savepoint("flow_sync")
		try:
			FlowSync(account_name).sync_account()
		except Exception:
			frappe.db.rollback(save_point="flow_sync")
			log("Error", "Flow", f"Flow sync failed for account {account_name}", account=account_name)


def known_status(meta_status: str | None, flow) -> str:
	"""The Select value for Meta's status. An unknown one keeps the Flow's current status, with a Warning."""
	if status := FLOW_STATUSES.get(meta_status):
		return status
	saved = not flow.is_new()
	log(
		"Warning",
		"Flow",
		f"Meta sent an unknown status {meta_status} for Flow {flow.flow_id}; it keeps {flow.status}",
		account=flow.whatsapp_account,
		reference_doctype="WA Flow" if saved else None,
		reference_docname=flow.name if saved else None,
	)
	return flow.status


class FlowSync:
	"""Mirrors the Flows of one WA Account from Meta."""

	def __init__(self, account_name: str):
		self.account_name = account_name
		self.business_id = frappe.db.get_value("WA Account", account_name, "business_id")
		self.client = _get_whatsapp_client(account_name)

	def sync_account(self) -> dict:
		counts = {"created": 0, "updated": 0, "removed": 0}
		listed = set()
		for row in self.client.get_flows():
			listed.add(row["id"])
			counts["created" if self.upsert(row["id"]) else "updated"] += 1
		counts["removed"] = self._remove_unlisted(listed)
		log(
			"Info",
			"Flow",
			f"Flow sync completed for account {self.account_name}: {counts}",
			account=self.account_name,
		)
		return counts

	def upsert(self, flow_id: str) -> bool:
		"""Return True when the Flow was new."""
		is_new = not frappe.db.exists("WA Flow", flow_id)
		# Locked before Meta is asked, so a status webhook that lands meanwhile waits instead of being overwritten.
		doc = frappe.new_doc("WA Flow") if is_new else frappe.get_doc("WA Flow", flow_id, for_update=True)
		details = self.client.get_flow(flow_id)
		doc.update(_flow_fields(details))
		if is_new or doc.business_id != self.business_id:
			doc.whatsapp_account = self.account_name
		doc.business_id = self.business_id
		doc.status = known_status(details.get("status"), doc)
		doc.flow_json = self._download_flow_json(flow_id, details) or doc.flow_json
		doc.flags.ignore_permissions = True
		doc.flags.from_sync = True
		doc.save()
		log(
			"Info",
			"Flow",
			f"{'Created' if is_new else 'Updated'} Flow {doc.flow_name} from sync (status={doc.status})",
			account=self.account_name,
			reference_doctype="WA Flow",
			reference_docname=doc.name,
		)
		return is_new

	def _remove_unlisted(self, listed: set[str]) -> int:
		removed = 0
		for name in frappe.get_all("WA Flow", filters={"whatsapp_account": self.account_name}, pluck="name"):
			if name not in listed and self._remove(name):
				removed += 1
		return removed

	def _remove(self, flow_name: str) -> bool:
		frappe.db.savepoint("remove_flow")
		try:
			frappe.delete_doc("WA Flow", flow_name, ignore_permissions=True)
		except frappe.LinkExistsError:
			# on_trash already deleted the Flow's logs.
			frappe.db.rollback(save_point="remove_flow")
			log(
				"Warning",
				"Flow",
				f"Flow {flow_name} is no longer on Meta but is kept, because other documents link to it",
				account=self.account_name,
				reference_doctype="WA Flow",
				reference_docname=flow_name,
			)
			return False
		log("Info", "Flow", f"Removed Flow {flow_name}: Meta no longer lists it", account=self.account_name)
		return True

	def _download_flow_json(self, flow_id: str, details: dict) -> str | None:
		try:
			assets = self.client.get_flow_assets(flow_id).get("data", [])
			url = next(asset["download_url"] for asset in assets if asset.get("asset_type") == "FLOW_JSON")
			return self.client.download_flow_json(url)
		except Exception:
			log(
				"Error",
				"Flow",
				f"Could not download the Flow JSON of Flow {details.get('name')} ({flow_id})",
				account=self.account_name,
			)
			return None


def _flow_fields(details: dict) -> dict:
	preview = details.get("preview") or {}
	errors = details.get("validation_errors")
	return {
		"flow_id": details["id"],
		"flow_name": details.get("name"),
		"categories": ", ".join(details.get("categories") or []),
		"json_version": details.get("json_version"),
		"endpoint_uri": details.get("endpoint_uri"),
		"validation_errors": frappe.as_json(errors) if errors else None,
		"preview_url": preview.get("preview_url"),
		"preview_expires_at": _to_system_time(preview.get("expires_at")),
	}


def _to_system_time(meta_time: str | None) -> datetime | None:
	if not meta_time:
		return None
	utc = datetime.strptime(meta_time, "%Y-%m-%dT%H:%M:%S%z")
	return convert_utc_to_system_timezone(utc).replace(tzinfo=None)
