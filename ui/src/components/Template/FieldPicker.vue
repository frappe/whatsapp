<script setup lang="ts">
import { computed } from "vue";
import { Button, Combobox } from "frappe-ui";
import type { ComboboxOption } from "frappe-ui";
import type { Loaded } from "./types";

// A Combobox over options the controller loads: shows their load state, and a failed load
// with a retry inside the popover, where the user went looking for them.
const props = defineProps<{
	modelValue: string;
	options: Loaded<ComboboxOption[]> | null;
	placeholder?: string;
	disabled?: boolean;
	ariaLabel: string;
	errorLabel: string;
	retryLabel: string;
}>();

const emit = defineEmits<{ "update:modelValue": [value: string] }>();

const items = computed(() => props.options?.data ?? []);
</script>

<template>
	<Combobox
		:model-value="modelValue || null"
		:options="items"
		:placeholder="placeholder"
		:disabled="disabled || !options"
		:loading="options?.loading && !items.length"
		:aria-label="ariaLabel"
		open-on-click
		@update:model-value="
			(value) => emit('update:modelValue', value == null ? '' : String(value))
		"
	>
		<template v-if="options?.error" #empty>
			<div
				class="flex items-center justify-between gap-2 px-2.5 py-1.5 text-sm text-ink-gray-6"
			>
				{{ errorLabel }}
				<Button size="sm" variant="ghost" :label="retryLabel" @click="options.retry()" />
			</div>
		</template>
	</Combobox>
</template>
