frappe.listview_settings["WhatsApp Template"] = {
	hide_name_column: true,
	onload: function (listview) {
		listview.page.add_button(__("Sync from Meta"), () => {
			frappe.call({
				method: "whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.sync_all",
				callback: function (r) {
					if (r.message?.accounts?.length > 1) {
						let options = r.message.accounts.map((acc) => acc.account_name);
						let d = new frappe.ui.Dialog({
							title: __("Select Account"),
							fields: [
								{
									fieldtype: "Select",
									fieldname: "account",
									label: __("WhatsApp Account"),
									options: options,
									reqd: 1,
								},
							],
							primary_action: function () {
								let account_name = d.get_value("account");
								frappe.call({
									method: "whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.sync_from_account",
									args: { account_name: account_name },
									callback: function (res) {
										d.hide();
										frappe.msgprint(
											__(
												`Synced ${res.message.total_synced} templates, skipped ${res.message.total_skipped}`
											)
										);
										listview.refresh();
									},
								});
							},
						});
						d.show();
					} else if (r.message?.total_synced !== undefined) {
						frappe.msgprint(
							__(
								`Synced ${r.message.total_synced} templates, skipped ${r.message.total_skipped}`
							)
						);
						listview.refresh();
					}
				},
			});
		});
	},
};
