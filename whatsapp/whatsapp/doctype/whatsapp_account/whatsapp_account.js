// Copyright (c) 2026, pratham@frappe.io and contributors
// For license information, please see license.txt

frappe.ui.form.on("Whatsapp Account", {
	refresh: function (frm) {
		_update_all_field_options(frm);
	},
});

frappe.ui.form.on("Whatsapp Account Append", {
	append_to: function (frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		row.sender_field = "";
		row.sender_name_field = "";
		frm.refresh_field("append_actions");
		_update_all_field_options(frm);
	},
});

async function _update_all_field_options(frm) {
	const rows = frm.doc.append_actions || [];
	if (!rows.length) return;

	const doctypes = [...new Set(rows.filter((r) => r.append_to).map((r) => r.append_to))];

	const cache = {};
	for (const dt of doctypes) {
		const response = await frappe.call({
			method: "whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.get_doctype_columns",
			args: { doctype: dt },
		});
		cache[dt] = response.message || [];
	}

	const allOptions = doctypes.flatMap((dt) => cache[dt]);
	const opts = allOptions.join("\n");

	frm.fields_dict.append_actions.grid.update_docfield_property("sender_field", "options", opts);
	frm.fields_dict.append_actions.grid.update_docfield_property(
		"sender_name_field",
		"options",
		opts,
	);
}
