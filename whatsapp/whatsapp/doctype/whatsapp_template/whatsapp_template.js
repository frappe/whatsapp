// Copyright (c) 2026, pratham@frappe.io and contributors
// For license information, please see license.txt

frappe.ui.form.on("Whatsapp Template", {
	refresh: function (frm) {},
	// triggered when a template variable is added
	template_variable_added: function (frm) {
		let body_variables = get_template_variables(frm.doc.message);
		let header_variables = get_template_variables(frm.doc.header_text);

		const variables = Array.from(new Set([...header_variables, ...body_variables]));

		if (variables.length) {
			frm.set_df_property("template_variables", "hidden", 0);
			frm.set_value(
				"template_variables",
				variables.map((v) => ({ variable_name: v, variable_example: "" })),
			);
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

function get_template_variables(text) {
	if (!text) return [];
	return text.match(/\{\{(\w+)\}\}/g) || [];
}
