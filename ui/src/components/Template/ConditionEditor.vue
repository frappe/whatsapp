<script setup lang="ts">
import { onBeforeUnmount, shallowRef } from "vue";
import { FormLabel } from "frappe-ui";
import { CodeEditor, CodeEditorContent, CodeKit, loadLanguage } from "frappe-ui/code-editor";
import type { Completion, CompletionContext, CompletionResult } from "@codemirror/autocomplete";
import type { Extension } from "@codemirror/state";
import { EditorView, tooltips } from "@codemirror/view";
import type { FlowButtonChrome } from "./flowChrome";
import type { FlowOutline, VariableItem } from "./types";

const props = defineProps<{
	modelValue: string;
	chrome: FlowButtonChrome;
	outline: FlowOutline | undefined;
	/** fields of the reference DocType, offered after `doc.` */
	docFields: VariableItem[];
	disabled: boolean;
}>();

const emit = defineEmits<{ "update:modelValue": [value: string] }>();

// The WA Message fields a condition is likely to test; `message` is the whole row.
const MESSAGE_FIELDS = [
	"from",
	"to",
	"whatsapp_account",
	"reference_doctype",
	"reference_docname",
	"flow",
	"flow_response",
	"timestamp",
];

function namespaces(): Completion[] {
	return [
		{ label: "response", type: "variable", detail: props.chrome.conditionResponse },
		{ label: "doc", type: "variable", detail: props.chrome.conditionDoc },
		{ label: "message", type: "variable", detail: props.chrome.conditionMessage },
	];
}

function members(namespace: string): Completion[] {
	if (namespace === "response") {
		return (props.outline?.answers ?? []).map((answer) => ({
			label: answer.key,
			type: "property",
			detail: answer.label || undefined,
		}));
	}
	if (namespace === "doc") {
		return props.docFields.map((field) => ({
			label: field.value,
			type: "property",
			detail: field.label,
		}));
	}
	return MESSAGE_FIELDS.map((field) => ({ label: field, type: "property" }));
}

function complete(context: CompletionContext): CompletionResult | null {
	const member = context.matchBefore(/\b(response|doc|message)\.\w*$/);
	if (member) {
		const namespace = member.text.slice(0, member.text.indexOf("."));
		return {
			from: member.from + namespace.length + 1,
			options: members(namespace),
			validFor: /^\w*$/,
		};
	}
	const word = context.matchBefore(/\w+$/);
	if (!word && !context.explicit) return null;
	return { from: word?.from ?? context.pos, options: namespaces(), validFor: /^\w*$/ };
}

const kit = CodeKit.configure({
	foldGutter: false,
	autocompletion: { override: [complete], activateOnTyping: true },
	placeholder: "response.rating < 3",
});
// CodeMirror's content is not a labelable element, so the label reaches it as an attribute.
const label = EditorView.contentAttributes.of({ "aria-label": props.chrome.conditionLabel });
// The editor box clips its overflow, so the completion list is drawn on <body> instead. A host
// dialog dismisses on a pointerdown outside it, so the list's own pointerdowns stop here.
// The layer takes frappe-ui's `frappe-code` class, under which its popup colours are scoped.
const popupLayer = document.createElement("div");
popupLayer.className = "frappe-code";
popupLayer.addEventListener("pointerdown", (event) => event.stopPropagation());
document.body.append(popupLayer);
onBeforeUnmount(() => popupLayer.remove());
const popups = tooltips({ parent: popupLayer });
const extensions = shallowRef<Extension[]>([kit, label, popups]);
// Python highlighting is an optional peer of frappe-ui; without it the text is plain.
loadLanguage("python")
	.then((python) => {
		if (python) extensions.value = [kit, label, popups, python];
	})
	.catch(() => {});
</script>

<template>
	<div class="flex min-w-0 flex-col gap-1.5">
		<FormLabel :label="chrome.conditionLabel" />
		<CodeEditor
			:model-value="modelValue"
			:extensions="extensions"
			:editable="!disabled"
			@update:model-value="(value) => emit('update:modelValue', value)"
		>
			<CodeEditorContent class="condition-editor" />
		</CodeEditor>
		<p class="text-p-sm text-ink-gray-5">{{ chrome.conditionHint }}</p>
	</div>
</template>

<style scoped>
.condition-editor {
	min-width: 0;
	--code-min-height: calc(2lh + 2 * var(--code-padding-y, 6px));
	--code-max-height: 8rem;
}
</style>

<style>
/* On <body> under a host dialog, which disables pointer events outside itself and sits above the page. */
.cm-tooltip.cm-tooltip-autocomplete {
	pointer-events: auto;
	z-index: 10000;
}
</style>
