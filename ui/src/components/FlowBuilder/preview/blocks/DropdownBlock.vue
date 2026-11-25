<script setup lang="ts">
import { computed } from "vue";
import type { Block } from "../../model";
import { useBuilder } from "../../context";
import { answerText } from "../sample";
import { usePhoneBlock } from "../phone";
import PhoneField from "./PhoneField.vue";

/** A field that opens the full-screen option list; ⊗ clears the choice. */
const props = defineProps<{ block: Block }>();
const { chrome } = useBuilder();
const { phone, component, name, text: value } = usePhoneBlock(props);
const label = computed(() => phone.text(component.value.label));
</script>

<template>
	<PhoneField :label="label" :required="component.required === true" :filled="!!value">
		<button
			type="button"
			class="absolute inset-0"
			:aria-label="label"
			aria-haspopup="listbox"
			@click="phone.openSheet(block)"
		/>
		<span class="min-w-0 flex-1 truncate text-[13px] text-[var(--wa-ink)]">
			{{ phone.text(answerText(block, value)) }}
		</span>
		<button
			v-if="value"
			type="button"
			class="relative flex size-6 shrink-0 items-center justify-center text-[var(--wa-ink-2)]"
			:aria-label="chrome.phoneClear"
			@click.stop="phone.run.set(name, '')"
		>
			<span class="lucide-circle-x size-4" aria-hidden="true" />
		</button>
		<span
			v-else
			class="lucide-chevron-down size-4 shrink-0 text-[var(--wa-ink-2)]"
			aria-hidden="true"
		/>
	</PhoneField>
</template>
