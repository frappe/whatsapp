<script setup lang="ts">
import { computed } from "vue";
import { FormLabel, TextInput } from "frappe-ui";
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
		<div class="divide-y divide-outline-gray-1 rounded-4 border border-outline-gray-2">
			<div
				v-for="(row, index) in rows"
				:key="row.variable_name"
				class="grid grid-cols-2 items-center gap-3 px-3 py-2"
			>
				<div class="flex min-w-0 flex-col">
					<span class="truncate text-base text-ink-gray-8">
						{{ labels.get(row.variable_name) ?? row.variable_name }}
					</span>
					<span class="truncate font-mono text-p-xs text-ink-gray-5">
						{{ braced(row.variable_name) }}
					</span>
				</div>
				<TextInput
					:model-value="row.variable_example"
					:placeholder="field.placeholder"
					:disabled="field.readOnly"
					:aria-label="`Example for ${labels.get(row.variable_name) ?? row.variable_name}`"
					@update:model-value="(value: string) => setExample(index, value)"
					@blur="emit('change', rows)"
				/>
			</div>
		</div>
	</div>
</template>
