<script setup lang="ts">
import { computed } from "vue";
import type { Block } from "../../model";
import { usePhone } from "../phone";
import PhoneField from "./PhoneField.vue";

/** Date picker and Calendar: a field that opens the device's date picker. */
const props = defineProps<{ block: Block }>();
const phone = usePhone();

const component = computed(() => props.block.component);
const name = computed(() => String(component.value.name ?? ""));
const value = computed(() => {
	const answer = phone.run.value(name.value);
	return typeof answer === "string" ? answer : "";
});
const shown = computed(() => {
	const date = new Date(`${value.value}T00:00:00`);
	return Number.isNaN(date.getTime())
		? value.value
		: new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
});
const label = computed(() => phone.text(component.value.label ?? component.value.title));
</script>

<template>
	<PhoneField
		:label="label"
		:required="component.required === true"
		:filled="!!value"
		:helper="phone.text(component['helper-text'])"
	>
		<span class="min-w-0 flex-1 truncate text-[13px] text-[var(--wa-ink)]">{{ shown }}</span>
		<span class="lucide-calendar size-4 shrink-0 text-[var(--wa-ink-2)]" aria-hidden="true" />
		<input
			class="absolute inset-0 cursor-pointer opacity-0"
			type="date"
			:aria-label="label"
			:value="value"
			@click="($event.target as HTMLInputElement).showPicker?.()"
			@input="phone.run.set(name, ($event.target as HTMLInputElement).value)"
		/>
	</PhoneField>
</template>
