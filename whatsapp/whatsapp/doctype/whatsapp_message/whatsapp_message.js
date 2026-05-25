// Copyright (c) 2026, pratham@frappe.io and contributors
// For license information, please see license.txt

frappe.ui.form.on("Whatsapp Message", {
	refresh: function (frm) {
		frm.trigger("is_template");
		if (frm.is_new() && frm.doc.direction === "Outgoing" && !frm.doc.whatsapp_account) {
			frappe.db.get_single_value("Whatsapp Setting", "default_account").then((account) => {
				if (account) frm.set_value("whatsapp_account", account);
			});
		}
	},

	is_template: function (frm) {
		frm.toggle_reqd("message", !frm.doc.is_template);
		frm.toggle_reqd("whatsapp_template", frm.doc.is_template);
		if (!frm.doc.is_template) {
			frm.toggle_reqd("reference_docname", false);
		}
	},

	whatsapp_template: function (frm) {
		if (frm.doc.whatsapp_template) {
			frappe.db.get_value(
				"Whatsapp Template",
				frm.doc.whatsapp_template,
				["reference_doctype", "message", "header_text"],
				(r) => {
					frm.set_value("reference_doctype", r.reference_doctype || null);
					frm.set_value("reference_docname", null);
					const has_vars = has_template_variables(r.message) || has_template_variables(r.header_text);
					frm.toggle_reqd("reference_docname", has_vars);
				},
			);
		} else {
			frm.set_value("reference_doctype", null);
			frm.set_value("reference_docname", null);
			frm.toggle_reqd("reference_docname", false);
		}
	},

	direction: function (frm) {
		if (frm.doc.direction == "Incoming") {
			frm.set_read_only();
		}
	},
});

function has_template_variables(text) {
	if (!text) return false;
	return /\{\{(\w+)\}\}/.test(text);
}
