# Copyright (c) 2026, pratham@frappe.io and Contributors
# See license.txt

import logging

import frappe
import requests


class WhatsApp:
	def __init__(self, args):
		self.business_id = args.business_id
		self.app_id = args.app_id
		self.access_token = args.access_token
		self.phone_number_id = args.phone_number_id
		self.base_url = getattr(args, "base_url", "https://graph.facebook.com")
		self.api_version = getattr(args, "api_version", "v23.0")
		self.account_name = getattr(args, "account_name", None)

	def _request(self, method, endpoint, **kwargs):
		url = f"{self.base_url}/{self.api_version}/{endpoint}"
		headers = {
			"Authorization": f"Bearer {self.access_token}",
			"Content-Type": "application/json",
		}
		if "headers" in kwargs:
			headers.update(kwargs.pop("headers"))
		resp = requests.request(method, url, headers=headers, **kwargs)
		try:
			resp.raise_for_status()
		except requests.HTTPError:
			body = resp.text
			logging.getLogger("whatsapp").error(
				"Meta API error | status=%s url=%s body=%s", resp.status_code, url, body
			)
			error_msg = _extract_meta_error(body)
			self._log_api_error(method, url, kwargs.get("json"), resp)
			raise requests.HTTPError(error_msg)
		result = resp.json()
		self._log_api_success(method, url, kwargs.get("json"), result)
		return result

	def _log_api_error(
		self, method: str, url: str, payload: dict | None, resp: requests.Response
	) -> None:
		try:
			event_type = "API"
			if "message_templates" in url or "/templates" in url:
				event_type = "Template"
			elif "/messages" in url:
				event_type = "Message"

			import frappe

			from whatsapp.whatsapp.api.utils import log

			log(
				"Error",
				event_type,
				f"Meta API {method} {url.rsplit('/', 1)[-1][:60]} failed: HTTP {resp.status_code}",
				account=self.account_name,
				request_data=payload,
				response_data=resp.text[:5000],
			)
		except Exception:
			pass

	def _log_api_success(self, method: str, url: str, payload: dict | None, result: dict) -> None:
		try:
			event_type = "API"
			if "message_templates" in url or "/templates" in url:
				event_type = "Template"
			elif "/messages" in url:
				event_type = "Message"

			from whatsapp.whatsapp.api.utils import log

			log(
				"Debug",
				event_type,
				f"Meta API {method} {url.rsplit('/', 1)[-1][:60]} succeeded",
				account=self.account_name,
				request_data=payload,
				response_data=result,
			)
		except Exception:
			pass

	def get_template(self, template_id):
		return self._request("GET", f"{template_id}")

	def get_template_list(self, filters=None):
		params = {}
		if filters:
			params.update(filters)
		return self._request("GET", f"{self.business_id}/message_templates", params=params)

	def create_template(self, data):
		return self._request("POST", f"{self.business_id}/message_templates", json=data)

	def update_template(self, template_id, data):
		return self._request("POST", f"{template_id}", json=data)

	def delete_template(self, template_id):
		return self._request("DELETE", f"{template_id}")

	def send_message(self, payload):
		payload.setdefault("messaging_product", "whatsapp")
		return self._request("POST", f"{self.phone_number_id}/messages", json=payload)

	def mark_as_read(self, message_id: str) -> dict:
		payload = {
			"messaging_product": "whatsapp",
			"status": "read",
			"message_id": message_id,
		}
		return self._request("POST", f"{self.phone_number_id}/messages", json=payload)

	def upload_media(self, file_content: bytes, mime_type: str, file_name: str) -> dict:
		url = f"{self.base_url}/{self.api_version}/{self.phone_number_id}/media"
		headers = {"Authorization": f"Bearer {self.access_token}"}
		files = {
			"file": (file_name, file_content, mime_type),
			"type": (None, mime_type),
			"messaging_product": (None, "whatsapp"),
		}
		resp = requests.post(url, headers=headers, files=files)
		try:
			resp.raise_for_status()
		except requests.HTTPError:
			error_msg = _extract_meta_error(resp.text)
			self._log_api_error("POST", url, {"file": file_name, "type": mime_type}, resp)
			raise requests.HTTPError(error_msg)
		result = resp.json()
		self._log_api_success("POST", url, {"file": file_name, "type": mime_type}, result)
		return result


def _extract_meta_error(body: str) -> str:
	try:
		data = requests.json_decoder.decode(body)
		error = data.get("error", {})
		if error.get("error_user_msg"):
			return error["error_user_msg"]
		if error.get("error_user_title"):
			return error["error_user_title"]
		if error.get("message"):
			return f"Code {error['code']}: {error['message']}"
	except Exception:
		pass
	return body
