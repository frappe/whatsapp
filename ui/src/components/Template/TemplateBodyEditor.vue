<script setup lang="ts">
import { ref, watch } from "vue";
import { FormLabel } from "frappe-ui";
import {
	Bold,
	Editor,
	EditorContent,
	EditorFixedMenu,
	Italic,
	Placeholder,
	StarterKit,
	Strike,
	SuggestionExtension,
} from "frappe-ui/editor";
import VariableSuggestionList from "./VariableSuggestionList.vue";
import { fromWhatsAppText, toWhatsAppText } from "./whatsappText";
import type { JsonNode } from "./whatsappText";
import type { TemplateBodyEditorProps, VariableItem } from "./types";

const props = defineProps<TemplateBodyEditorProps>();
const emit = defineEmits<{
	"update:modelValue": [value: string];
	change: [value: string];
}>();

// `Editor` reloads any object other than the one it last emitted, resetting the caret.
const content = ref<JsonNode>(fromWhatsAppText(props.modelValue as string));

watch(content, (json) => emit("update:modelValue", toWhatsAppText(json)));

watch(
	() => props.modelValue as string,
	(text) => {
		if (toWhatsAppText(content.value) !== (text ?? "")) content.value = fromWhatsAppText(text);
	}
);

const variables = SuggestionExtension.configure<VariableItem>({
	name: "templateVariables",
	trigger: "{{",
	items: (query) => {
		const needle = query.trim().toLowerCase();
		return props
			.fields()
			.filter((fieldname) => fieldname.includes(needle))
			.map((value) => ({ value }));
	},
	command: ({ editor, range, item }) =>
		editor.chain().focus().deleteRange(range).insertContent(`{{${item.value}}} `).run(),
	component: VariableSuggestionList,
});

// WhatsApp text supports only bold, italic, strike and line breaks.
const extensions = [
	StarterKit.configure({
		blockquote: false,
		bulletList: false,
		orderedList: false,
		listItem: false,
		listKeymap: false,
		heading: false,
		horizontalRule: false,
		code: false,
		codeBlock: false,
		link: false,
		underline: false,
		dropcursor: false,
		gapcursor: false,
		trailingNode: false,
	}),
	Placeholder,
	variables,
];

const toolbar = [Bold, Italic, Strike];
</script>

<template>
	<div class="flex flex-col gap-1.5">
		<FormLabel v-if="field.label" :label="field.label" :required="field.reqd" />
		<Editor
			v-model="content"
			format="json"
			:extensions="extensions"
			:placeholder="field.placeholder"
			:editable="!field.readOnly"
			@blur="emit('change', toWhatsAppText(content))"
		>
			<!-- `Editor` is renderless; without this wrapper the outer column's gap splits the toolbar from the content. -->
			<div>
				<div
					v-if="!field.readOnly"
					class="flex items-center rounded-t border border-b-0 border-outline-gray-2 bg-surface-gray-1 px-1 py-1"
				>
					<EditorFixedMenu :items="toolbar" />
				</div>
				<EditorContent
					class="max-h-80 min-h-32 overflow-auto rounded-b border border-outline-gray-2 bg-surface-white px-3 py-2 text-base text-ink-gray-8 prose-sm"
				/>
			</div>
		</Editor>
		<p v-if="field.description" class="text-p-xs text-ink-gray-5">{{ field.description }}</p>
	</div>
</template>
