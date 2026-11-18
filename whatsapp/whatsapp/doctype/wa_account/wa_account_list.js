frappe.listview_settings["WA Account"] = {
	get_indicator(doc) {
		const color = { Active: "green", Inactive: "gray", Disconnected: "red" }[doc.status];
		return [__(doc.status), color, `status,=,${doc.status}`];
	},
	onload() {
		const { whatsapp_connect: result, whatsapp_account: account } =
			frappe.utils.get_query_params();
		if (!result) return;
		history.replaceState(null, "", location.pathname);
		frappe
			.xcall("whatsapp.whatsapp.oauth.get_connect_message", { result, account })
			.then(({ message, indicator }) =>
				frappe.msgprint({ title: __("Connect with Meta"), message, indicator })
			);
	},
};
