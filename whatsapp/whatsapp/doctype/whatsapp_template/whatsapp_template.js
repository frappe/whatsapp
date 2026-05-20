// Copyright (c) 2026, pratham@frappe.io and contributors
// For license information, please see license.txt

frappe.ui.form.on("Whatsapp Template", {
	refresh: function (frm) {
		frm.trigger("template_variable_added");
	},

	update_variable_field_options: function (frm) {
		if (!frm.doc.reference_doctype) return;

		frappe
			.call({
				method: "whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.get_doctype_columns",
				args: { doctype: frm.doc.reference_doctype },
			})
			.then((r) => {
				const options = r.message || [];

				frm.set_df_property(
					"template_variables",
					"options",
					options,
					cur_frm.docname,
					"variable_field",
				);
			});
	},

	reference_doctype: function (frm) {
		frm.doc.template_variables?.forEach((row) => {
			row.variable_field = "";
		});
		frm.refresh_field("template_variables");
		frm.trigger("update_variable_field_options");
	},

	template_variable_added: function (frm, _doctype, _name, context) {
		let body_variables = get_template_variables(frm.doc.message);
		let header_variables = get_template_variables(frm.doc.header_text);

		const variables = Array.from(new Set([...header_variables, ...body_variables]));

		if (variables.length) {
			frm.set_df_property("template_variables", "hidden", 0);

			let existing = {};
			(frm.doc.template_variables || []).forEach((row) => {
				existing[row.variable_name] = row;
			});

			frm.set_value(
				"template_variables",
				variables.map((v) => ({
					variable_name: v,
					variable_example: existing[v]?.variable_example || "",
					variable_field: existing[v]?.variable_field || "",
				})),
			);
			frm.trigger("update_variable_field_options");
		} else {
			frm.set_df_property("template_variables", "hidden", 1);
		}
	},

	header_text: function (frm) {
		let header_variables = get_template_variables(frm.doc.header_text);
		if (header_variables.length) {
			frm.trigger("template_variable_added");
		}
	},

	message: function (frm) {
		let body_variables = get_template_variables(frm.doc.message);
		if (body_variables.length) {
			frm.trigger("template_variable_added");
		}
	},
});

frappe.ui.form.on("Template Variable", {
	variable_field: function (frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		row.variable_field = row.variable_field || "";
	},
});

function get_template_variables(text) {
	if (!text) return [];
	return (text.match(/\{\{(\w+)\}\}/g) || []).map((v) => v.replace(/[{}]/g, ""));
}
