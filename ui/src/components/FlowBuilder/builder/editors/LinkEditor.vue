<script setup lang="ts">
import { computed } from "vue";
import { updateBlock, type Block, type JsonObject, type Screen } from "../../model";
import CountedInput from "../CountedInput.vue";
import { useBlock } from "./useBlock";

/** Our Link: its text and the address it opens. */
const props = defineProps<{ block: Block; screen: Screen }>();
const { chrome, edit, actions, component, value, limit, error } = useBlock(props);

const url = computed(() =>
	String((component.value["on-click-action"] as JsonObject | undefined)?.url ?? "")
);

function setUrl(next: string) {
	edit((model) =>
		updateBlock(model, props.block.uid, { "on-click-action": { name: "open_url", url: next } })
	);
}
</script>

<template>
	<CountedInput
		data-main-field
		:label="chrome.textLabel"
		:model-value="value('text')"
		:limit="limit('text')"
		:error="error('text')"
		@update:model-value="(next) => actions.setText(block, next)"
	/>
	<CountedInput
		:label="chrome.urlLabel"
		placeholder="https://"
		:model-value="url"
		@update:model-value="setUrl"
	/>
</template>
