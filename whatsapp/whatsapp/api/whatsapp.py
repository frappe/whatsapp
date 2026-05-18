# Copyright (c) 2026, pratham@frappe.io and Contributors
# See license.txt

import requests


class Whatsapp:
	def __init__(self, args):
		self.business_id = args.business_id
		self.app_id = args.app_id
		self.access_token = args.access_token
		self.phone_number_id = args.phone_number_id
		self.base_url = getattr(args, "base_url", "https://graph.facebook.com")
		self.api_version = getattr(args, "api_version", "v22.0")

	def _request(self, method, endpoint, **kwargs):
		url = f"{self.base_url}/{self.api_version}/{endpoint}"
		headers = {
			"Authorization": f"Bearer {self.access_token}",
			"Content-Type": "application/json",
		}
		if "headers" in kwargs:
			headers.update(kwargs.pop("headers"))
		resp = requests.request(method, url, headers=headers, **kwargs)
		resp.raise_for_status()
		return resp.json()

	def get_template(self, template_id):
		return self._request("GET", f"{template_id}")

	def get_template_list(self, filters=None):
		params = {}
		if filters:
			params.update(filters)
		return self._request("GET", f"{self.business_id}/message_templates", params=params)

	def create_template(self, data):
		return self._request("POST", f"{self.business_id}/message_templates", json=data)

	def delete_template(self, template_id):
		return self._request("DELETE", f"{template_id}")

	def send_message(self, payload):
		payload.setdefault("messaging_product", "whatsapp")
		return self._request("POST", f"{self.phone_number_id}/messages", json=payload)
