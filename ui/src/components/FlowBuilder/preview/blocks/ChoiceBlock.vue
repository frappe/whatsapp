<script setup lang="ts">
import { computed } from "vue";
import { optionsOf, type Block, type JsonObject } from "../../model";
import { format } from "../../chrome";
import { useBuilder } from "../../context";
import { usePhoneBlock } from "../phone";
import type { Value } from "../sample";
import PhoneCheck from "./PhoneCheck.vue";

/** Single choice (RadioButtonsGroup) and Multiple choice (CheckboxGroup). */
const props = defineProps<{ block: Block }>();

const { chrome } = useBuilder();
const { phone, component, name, answer } = usePhoneBlock(props);

const multiple = computed(() => component.value.type === "CheckboxGroup");
const options = computed(() => optionsOf(component.value));
const chosen = computed(() => new Set(chosenIds(answer.value)));
const label = computed(() => {
	const text = phone.text(component.value.label);
	return component.value.required === true || !text
		? text
		: format(chrome.value.phoneOptional, text);
});

function chosenIds(value: Value | undefined): string[] {
	if (Array.isArray(value)) return value;
	if (typeof value === "string" && value) return [value];
	return [];
}

function choose(option: JsonObject) {
	if (option.enabled === false) return;
	const id = String(option.id);
	if (!multiple.value) return phone.run.set(name.value, id);
	const next = new Set(chosen.value);
	if (next.has(id)) next.delete(id);
	else next.add(id);
	phone.run.set(name.value, [...next]);
}
</script>

<template>
	<fieldset class="flex flex-col gap-2 border-b border-[var(--wa-divider)] pb-3">
		<legend v-if="label" class="pb-2 text-[13px] font-medium text-[var(--wa-ink)]">
			{{ label }}
		</legend>
		<p v-if="component.description" class="-mt-1 text-[11px] text-[var(--wa-ink-2)]">
			{{ phone.text(component.description) }}
		</p>
		<div class="flex flex-col">
			<button
				v-for="option in options"
				:key="String(option.id)"
				type="button"
				class="flex min-h-10 items-center gap-3 py-2 text-left"
				:class="option.enabled === false && 'opacity-50'"
				:role="multiple ? 'checkbox' : 'radio'"
				:aria-checked="chosen.has(String(option.id))"
				@click="choose(option)"
			>
				<span class="flex min-w-0 flex-1 flex-col">
					<span class="text-[13px] text-[var(--wa-ink)]">{{
						phone.text(option.title)
					}}</span>
					<span v-if="option.description" class="text-[11px] text-[var(--wa-ink-2)]">{{
						phone.text(option.description)
					}}</span>
				</span>
				<PhoneCheck
					:shape="multiple ? 'square' : 'round'"
					:on="chosen.has(String(option.id))"
				/>
			</button>
		</div>
	</fieldset>
</template>
