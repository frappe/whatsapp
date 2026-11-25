<script setup lang="ts">
import { computed } from "vue";
import { Select } from "frappe-ui";
import type { FieldMeta } from "@framework/ui/components/FormLayout";
import { FLOW_ICONS } from "../Messages/flowIcons";
import type { FlowButtonChrome } from "./flowChrome";

const props = defineProps<{
	field: FieldMeta;
	modelValue?: string | null;
	error?: string;
	chrome: FlowButtonChrome;
}>();
const emit = defineEmits<{ "update:modelValue": [value: string]; change: [value: string] }>();

const options = computed(() => [
	{ value: "", label: props.chrome.iconNone },
	{ value: "Document", label: props.chrome.iconDocument, icon: FLOW_ICONS.Document },
	{ value: "Promotion", label: props.chrome.iconPromotion, icon: FLOW_ICONS.Promotion },
	{ value: "Review", label: props.chrome.iconReview, icon: FLOW_ICONS.Review },
]);

function set(value: unknown) {
	const icon = String(value ?? "");
	emit("update:modelValue", icon);
	emit("change", icon);
}
</script>

<template>
	<Select
		:model-value="modelValue ?? ''"
		:options="options"
		:label="field.label"
		:error="error"
		:disabled="field.readOnly"
		@update:model-value="set"
	/>
</template>
