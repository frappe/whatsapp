const STATUS_COLORS = { Active: "green", Blocked: "red", Disabled: "gray" };

frappe.listview_settings["WA Profile"] = {
	filters: [["status", "!=", "Disabled"]],
	get_indicator(doc) {
		return [__(doc.status), STATUS_COLORS[doc.status], `status,=,${doc.status}`];
	},
};
