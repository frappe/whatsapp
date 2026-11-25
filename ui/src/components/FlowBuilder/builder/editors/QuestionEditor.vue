<script setup lang="ts">
import { computed } from "vue";
import { Select } from "frappe-ui";
import type { Block, Screen } from "../../model";
import CountedInput from "../CountedInput.vue";
import { INPUT_TYPES } from "../describe";
import { useBlock } from "./useBlock";

/** Short answer, Paragraph, Date picker, Calendar, Photo, Document and the label of a choice. */
const props = defineProps<{ block: Block; screen: Screen }>();
const { session, chrome, actions, type, value, set, limit, error } = useBlock(props);

const HELPER: Record<string, string> = {
	TextInput: "helper-text",
	TextArea: "helper-text",
	DatePicker: "helper-text",
	CalendarPicker: "helper-text",
	PhotoPicker: "description",
	DocumentPicker: "description",
};

const inputTypes = computed(() =>
	INPUT_TYPES.map((each) => ({ value: each, label: chrome.value[each] }))
);
const helper = computed(() => HELPER[type.value]);
</script>

<template>
	<Select
		v-if="type === 'TextInput'"
		:label="chrome.typeLabel"
		:options="inputTypes"
		:model-value="value('input-type') || 'text'"
		:disabled="session.readOnly"
		@update:model-value="(next) => set('input-type', String(next))"
	/>
	<CountedInput
		data-main-field
		:label="chrome.labelLabel"
		:model-value="value('label')"
		:limit="limit('label')"
		:error="error('label')"
		@update:model-value="(next) => actions.setText(block, next)"
	/>
	<CountedInput
		v-if="helper"
		optional
		:label="chrome.instructionsLabel"
		:model-value="value(helper)"
		:limit="limit(helper)"
		:error="error(helper)"
		@update:model-value="(next) => set(helper, next)"
	/>
</template>
