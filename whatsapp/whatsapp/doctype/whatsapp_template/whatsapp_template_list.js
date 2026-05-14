frappe.listview_settings["Whatsapp Template"] = {
	onload: function (listview) {
		listview.page.add_button(__("Sync from Meta"), () => {});
	},
};
