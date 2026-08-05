// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("WhatsApp Message", {
	refresh: function (frm) {
		frm.trigger("is_template");
		frm.trigger("direction");
		if (frm.is_new() && frm.doc.direction === "Outgoing" && !frm.doc.whatsapp_account) {
			frappe.db.get_single_value("WhatsApp Settings", "default_account").then((account) => {
				if (account) frm.set_value("whatsapp_account", account);
			});
		}
	},

	is_template: function (frm) {
		frm.toggle_reqd("message", !frm.doc.is_template && !frm.doc.attach);
		frm.toggle_reqd("whatsapp_template", frm.doc.is_template);
		if (!frm.doc.is_template) {
			frm.toggle_reqd("reference_docname", false);
		}
	},

	attach: function (frm) {
		frm.trigger("is_template");
	},

	whatsapp_template: function (frm) {
		if (frm.doc.whatsapp_template) {
			frappe.db.get_value(
				"WhatsApp Template",
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
		frm.toggle_display("reply_to_message", frm.doc.direction === "Outgoing");
	},

	reply_to_message: function (frm) {
		if (frm.doc.reply_to_message) {
			frappe.db.get_value("WhatsApp Message", frm.doc.reply_to_message, "message_id", (r) => {
				frm.set_value("context_message_id", r.message_id || null);
			});
		} else if (!frm.doc.context_message_id) {
			frm.set_value("context_message_id", null);
		}
	},
});

function has_template_variables(text) {
	if (!text) return false;
	return /\{\{(\w+)\}\}/.test(text);
}
