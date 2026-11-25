<script setup lang="ts">
import { computed } from "vue";
import { Select } from "frappe-ui";
import type { FieldMeta } from "@framework/ui/components/FormLayout";
import type { FlowButtonChrome } from "./flowChrome";

// Lucide stand-ins for the three icons WhatsApp draws on a Flow button.
const ICONS = { Document: "lucide-file-text", Promotion: "lucide-tag", Review: "lucide-star" };

const props = defineProps<{
	field: FieldMeta;
	modelValue?: string | null;
	error?: string;
	chrome: FlowButtonChrome;
}>();
const emit = defineEmits<{ "update:modelValue": [value: string]; change: [value: string] }>();

const options = computed(() => [
	{ value: "", label: props.chrome.iconNone },
	{ value: "Document", label: props.chrome.iconDocument, icon: ICONS.Document },
	{ value: "Promotion", label: props.chrome.iconPromotion, icon: ICONS.Promotion },
	{ value: "Review", label: props.chrome.iconReview, icon: ICONS.Review },
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
