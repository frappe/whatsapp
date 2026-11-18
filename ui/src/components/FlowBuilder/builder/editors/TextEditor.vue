<script setup lang="ts">
import { computed } from "vue";
import { Select } from "frappe-ui";
import { TEXT_TYPES, changeTextType, type Block, type Screen } from "../../model";
import CountedInput from "../CountedInput.vue";
import { useBlock } from "./useBlock";

/**
 * Large heading, Small heading, Body and Caption share Meta's editor; Rich text has no Type. Rich
 * text written as a list of lines is saved back as one string, which Meta also accepts.
 */
const props = defineProps<{ block: Block; screen: Screen }>();
const { session, chrome, edit, actions, component, type, limit, error } = useBlock(props);

const types = computed(() =>
	TEXT_TYPES.map((value) => ({ value, label: chrome.value[value as keyof typeof chrome.value] }))
);
const text = computed(() => {
	const value = component.value.text;
	if (Array.isArray(value)) return value.join("\n");
	return typeof value === "string" ? value : "";
});
</script>

<template>
	<Select
		v-if="TEXT_TYPES.includes(type)"
		:label="chrome.typeLabel"
		:options="types"
		:model-value="type"
		:disabled="session.readOnly"
		@update:model-value="
			(value) => edit((model) => changeTextType(model, block.uid, String(value)))
		"
	/>
	<CountedInput
		multiline
		data-main-field
		:label="chrome.textLabel"
		:model-value="text"
		:limit="limit('text')"
		:error="error('text')"
		@update:model-value="(value) => actions.setText(block, value)"
	/>
</template>
