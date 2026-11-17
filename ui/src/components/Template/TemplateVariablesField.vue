<script setup lang="ts">
import { computed } from "vue";
import { FormLabel } from "frappe-ui";
import type { TemplateVariablesFieldProps, TemplateVariableRow } from "./types";

// Rows follow the `{{variables}}` in the text, so the only thing to edit is each example.
const props = defineProps<TemplateVariablesFieldProps>();
const emit = defineEmits<{
	"update:modelValue": [rows: TemplateVariableRow[]];
	change: [rows: TemplateVariableRow[]];
}>();

const rows = computed(() => (props.modelValue as TemplateVariableRow[]) ?? []);

const labels = computed(
	() => new Map(props.fields().map((field) => [field.value, field.label]))
);

// Built in script: a literal `}}` in the template would close the interpolation.
function braced(name: string) {
	return `{{${name}}}`;
}

function labelOf(name: string) {
	return labels.value.get(name) ?? name;
}

function setExample(index: number, example: string) {
	const next = rows.value.map((row, i) =>
		i === index ? { ...row, variable_example: example } : row
	);
	emit("update:modelValue", next);
}
</script>

<template>
	<div class="flex flex-col gap-1.5">
		<FormLabel v-if="field.label" :label="field.label" />
		<p v-if="field.description" class="text-p-xs text-ink-gray-5">{{ field.description }}</p>
		<div class="overflow-hidden rounded-4 border border-outline-gray-2">
			<div class="grid grid-cols-2 bg-surface-gray-2 text-sm text-ink-gray-5">
				<div class="truncate border-r border-outline-gray-2 px-2 py-2">Variable</div>
				<div class="truncate px-2 py-2">Example <span class="text-ink-red-5">*</span></div>
			</div>
			<div
				v-for="(row, index) in rows"
				:key="row.variable_name"
				class="grid grid-cols-2 border-t border-outline-gray-2 bg-surface-base"
			>
				<div
					class="flex min-w-0 items-center border-r border-outline-gray-2 px-2 text-sm text-ink-gray-7"
					:title="braced(row.variable_name)"
				>
					<span class="truncate">{{ labelOf(row.variable_name) }}</span>
				</div>
				<input
					type="text"
					class="h-[34px] w-full min-w-0 border-none bg-surface-base px-2 text-sm text-ink-gray-8 placeholder-ink-gray-4 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-outline-gray-3 disabled:text-ink-gray-5"
					:value="row.variable_example"
					:placeholder="field.placeholder"
					:disabled="field.readOnly"
					:aria-label="`Example for ${labelOf(row.variable_name)}`"
					@input="setExample(index, ($event.target as HTMLInputElement).value)"
					@blur="emit('change', rows)"
				/>
			</div>
		</div>
	</div>
</template>
