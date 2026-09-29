<script setup lang="ts">
import { computed } from "vue";
import TemplateContent from "../Messages/TemplateContent.vue";
import { fillVariables } from "./variables";
import type { TemplatePreviewProps } from "./types";

const props = defineProps<TemplatePreviewProps>();

const doc = computed(() => props.controller.doc);

const examples = computed(
	() =>
		new Map(
			doc.value.template_variables.map((row) => [row.variable_name, row.variable_example])
		)
);

const header = computed(() =>
	doc.value.header_type === "Text" ? fillVariables(doc.value.header_text, examples.value) : ""
);
const body = computed(() => fillVariables(doc.value.message, examples.value));
</script>

<template>
	<div class="max-w-sm rounded-lg bg-surface-gray-1 p-3 text-p-sm text-ink-gray-9">
		<TemplateContent
			v-if="header || body"
			:header="header"
			:body="body"
			:footer="doc.footer"
			:buttons="doc.buttons"
		/>
		<div v-else class="text-ink-gray-5">Type a message to preview it here</div>
	</div>
</template>
