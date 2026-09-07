// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

const MAPPING_FIELDS = ["message_field", "sender_field", "sender_name_field", "timestamp_field"];

frappe.ui.form.on("WhatsApp Account", {
	setup: function (frm) {
		// set here rather than on refresh: a grid control keeps the get_query it was
		// created with, and the first rows render before any refresh handler runs
		for (const fieldname of MAPPING_FIELDS) {
			frm.set_query(fieldname, "append_actions", (doc, cdt, cdn) => ({
				query: "whatsapp.whatsapp.doctype.whatsapp_account.whatsapp_account.get_append_field_options",
				params: {
					target_doctype: locals[cdt][cdn].append_to || "",
					slot: fieldname,
				},
			}));
		}
	},
});

frappe.ui.form.on("WhatsApp Account Append", {
	append_to: function (frm, cdt, cdn) {
		// the mapped fieldnames belong to the doctype that was just replaced
		const cleared = {};
		for (const fieldname of MAPPING_FIELDS) {
			cleared[fieldname] = "";
		}
		frappe.model.set_value(cdt, cdn, cleared);
	},
});
