// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

const MANAGE_MODULE = "whatsapp.whatsapp.flows.manage";
const DEPRECATABLE_STATUSES = ["Published", "Throttled", "Blocked"];

frappe.ui.form.on("WA Flow", {
	refresh: function (frm) {
		render_validation_errors(frm);
		frm.set_intro(
			frm.doc.status === "Deprecated"
				? __("This Flow is deprecated. It can't be changed or sent.")
				: ""
		);
		add_actions(frm);
	},
});

function add_actions(frm) {
	frm.add_custom_button(__("Refresh from Meta"), () =>
		run_flow_action(frm, "refresh_flow", __("Refreshing the Flow from Meta..."))
	);

	if (frm.doc.status === "Draft") {
		const publish = frm.add_custom_button(__("Publish"), () =>
			run_flow_action(frm, "publish_flow", __("Publishing the Flow..."))
		);
		if (frm.doc.validation_errors) {
			publish
				.prop("disabled", true)
				.attr("title", __("Fix the validation errors before you publish the Flow."));
		}
	}

	if (DEPRECATABLE_STATUSES.includes(frm.doc.status)) {
		frm.add_custom_button(__("Deprecate"), () =>
			frappe.confirm(
				__(
					"Deprecate this Flow? This can't be undone: it can't be sent or published again."
				),
				() => run_flow_action(frm, "deprecate_flow", __("Deprecating the Flow..."))
			)
		);
	}

	if (frm.doc.preview_url) {
		frm.add_custom_button(__("Open preview"), () =>
			window.open(frm.doc.preview_url, "_blank", "noopener")
		);
	}
}

function run_flow_action(frm, method, freeze_message) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the Flow first."));
		return;
	}
	frappe.call({
		method: `${MANAGE_MODULE}.${method}`,
		args: { name: frm.doc.name },
		freeze: true,
		freeze_message: freeze_message,
		callback: () => frm.reload_doc(),
	});
}

function render_validation_errors(frm) {
	const errors = JSON.parse(frm.doc.validation_errors || "[]");
	const items = errors.map((error) => `<li>${describe_validation_error(error)}</li>`).join("");
	frm.get_field("validation_errors_html").$wrapper.html(
		`<p class="text-danger">${__(
			"Meta reports these validation errors:"
		)}</p><ul>${items}</ul>`
	);
}

function describe_validation_error(error) {
	const escape = frappe.utils.escape_html;
	const paths = (error.pointers || []).map((pointer) => pointer.path).filter(Boolean);
	let text = escape(error.message || error.error || "");
	if (error.line_start != null) {
		text = `${__("Line {0}, column {1}", [error.line_start, error.column_start])} — ${text}`;
	}
	if (paths.length) {
		text += ` (${escape(paths.join(", "))})`;
	}
	return text;
}
