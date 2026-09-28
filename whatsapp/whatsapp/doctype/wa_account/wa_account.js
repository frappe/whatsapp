// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

const MAPPING_FIELDS = ["message_field", "sender_field", "sender_name_field", "timestamp_field"];

frappe.ui.form.on("WA Account", {
	refresh: function (frm) {
		if (frm.is_new()) return;
		frm.page.add_menu_item(__("Check Webhook Subscription"), () => {
			frappe.call({
				method: "whatsapp.whatsapp.doctype.wa_account.wa_account.check_webhook_subscription",
				args: { account: frm.doc.name },
				freeze: true,
				freeze_message: __("Asking Meta which apps are subscribed..."),
				callback: (r) => show_subscription_result(frm, r.message),
			});
		});
	},

	setup: function (frm) {
		// set here rather than on refresh: a grid control keeps the get_query it was
		// created with, and the first rows render before any refresh handler runs
		frm.set_query("append_to", "append_actions", () => ({
			filters: { istable: 0, issingle: 0 },
		}));
		for (const fieldname of MAPPING_FIELDS) {
			frm.set_query(fieldname, "append_actions", (doc, cdt, cdn) => ({
				query: "whatsapp.whatsapp.doctype.wa_account.wa_account.get_append_field_options",
				params: {
					target_doctype: locals[cdt][cdn].append_to || "",
					slot: fieldname,
				},
			}));
		}
	},
});

frappe.ui.form.on("WA Account Append", {
	append_to: function (frm, cdt, cdn) {
		// the mapped fieldnames belong to the doctype that was just replaced
		const cleared = {};
		for (const fieldname of MAPPING_FIELDS) {
			cleared[fieldname] = "";
		}
		frappe.model.set_value(cdt, cdn, cleared);
	},
});

function show_subscription_result(frm, result) {
	const escape = frappe.utils.escape_html;
	const waba = escape(frm.doc.business_id);
	const apps = result.subscribed_apps
		.map((app) => `<li>${escape(app.name || "")} (${escape(app.id || "")})</li>`)
		.join("");

	if (result.subscribed) {
		frappe.msgprint({
			title: __("Webhook Subscription"),
			indicator: "green",
			message: `${__("The app is subscribed to WABA {0}.", [waba])}<ul>${apps}</ul>`,
		});
		return;
	}

	const expected = frm.doc.app_id
		? __("Expected App ID: {0}", [escape(frm.doc.app_id)])
		: __("No App ID is set on this account, so any subscribed app would count.");
	const dialog = new frappe.ui.Dialog({
		title: __("Webhook Subscription"),
		indicator: "orange",
		primary_action_label: __("Subscribe"),
		primary_action: () => {
			frappe.call({
				method: "whatsapp.whatsapp.doctype.wa_account.wa_account.subscribe_webhook",
				args: { account: frm.doc.name },
				freeze: true,
				freeze_message: __("Subscribing the app to the WABA..."),
				callback: (r) => {
					dialog.hide();
					show_subscription_result(frm, r.message);
				},
			});
		},
	});
	dialog.$body
		.html(`<p>${__("The app is not subscribed to WABA {0}, so it receives no webhook events.", [waba])}</p>
		<p>${expected}</p>
		<p>${__("Subscribed apps:")}</p>
		<ul>${apps || `<li>${__("none")}</li>`}</ul>
		<p>${__("Subscribe uses this account's access token, so the app that token belongs to is the one that gets subscribed.")}</p>`);
	dialog.show();
}
