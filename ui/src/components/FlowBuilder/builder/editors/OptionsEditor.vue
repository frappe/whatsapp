<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { Button, FormLabel, Tooltip } from "frappe-ui";
import {
	DROPDOWN_MAX_WITH_IMAGES,
	OPTION_COUNTS,
	OPTION_LIMITS,
	addOption,
	removeOption,
	updateOption,
	type Block,
	type JsonObject,
	type Screen,
} from "../../model";
import { format } from "../../chrome";
import CountedInput from "../CountedInput.vue";
import { useBlock } from "./useBlock";

/** Meta's options: one input per option with its counter and a delete, then "Add option". */
const props = defineProps<{ block: Block; screen: Screen }>();
const { session, chrome, edit, component, type, error } = useBlock(props);

const list = ref<HTMLElement>();

const options = computed(() => component.value["data-source"] as JsonObject[]);
const counts = computed(() => OPTION_COUNTS[type.value]);
const max = computed(() =>
	type.value === "Dropdown" && options.value.some((option) => option.image)
		? DROPDOWN_MAX_WITH_IMAGES
		: counts.value.max
);
const addReason = computed(() =>
	options.value.length >= max.value ? format(chrome.value.maxOptions, max.value) : ""
);
const removeReason = computed(() => {
	if (options.value.length > counts.value.min) return "";
	return counts.value.min === 1
		? chrome.value.minOption
		: format(chrome.value.minOptions, counts.value.min);
});

async function add(index = options.value.length) {
	if (addReason.value) return;
	edit((model) => addOption(model, props.block.uid, { title: chrome.value.newOption }, index));
	await nextTick();
	const input = list.value?.querySelectorAll<HTMLInputElement>("input")[index];
	input?.focus();
	input?.select();
}

function setTitle(index: number, title: string) {
	edit((model) => updateOption(model, props.block.uid, index, { title }));
}
</script>

<template>
	<div class="flex flex-col gap-1.5">
		<FormLabel :label="chrome.optionsLabel" />
		<ul ref="list" class="flex flex-col gap-2">
			<li
				v-for="(option, index) in options"
				:key="`${option.id}:${index}`"
				class="flex items-start gap-1"
			>
				<CountedInput
					class="min-w-0 flex-1"
					:aria-label="`${chrome.newOption} ${index + 1}`"
					:model-value="String(option.title ?? '')"
					:limit="OPTION_LIMITS.title"
					:error="error(`data-source[${index}].title`)"
					@update:model-value="(title) => setTitle(index, title)"
					@keydown.enter.prevent="add(index + 1)"
				/>
				<Tooltip v-if="!session.readOnly" :text="removeReason" :disabled="!removeReason">
					<span :tabindex="removeReason ? 0 : undefined">
						<Button
							variant="ghost"
							icon="lucide-trash-2"
							:aria-label="chrome.removeOption"
							:disabled="!!removeReason"
							@click="edit((model) => removeOption(model, block.uid, index))"
						/>
					</span>
				</Tooltip>
			</li>
		</ul>
		<Tooltip v-if="!session.readOnly" :text="addReason" :disabled="!addReason">
			<span class="self-start" :tabindex="addReason ? 0 : undefined">
				<Button
					variant="subtle"
					icon-left="lucide-plus"
					:label="chrome.addOption"
					:disabled="!!addReason"
					@click="add()"
				/>
			</span>
		</Tooltip>
	</div>
</template>
