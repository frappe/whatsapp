<script setup lang="ts">
import { computed } from "vue";
import { Button } from "frappe-ui";
import { addReadMore, readMoreOf, removeReadMore, type Block, type Screen } from "../../model";
import CountedInput from "../CountedInput.vue";
import { useBlock } from "./useBlock";

/** Meta's Opt-in: the label, then a "Read more" screen of its own that the label links to. */
const props = defineProps<{ block: Block; screen: Screen }>();
const { session, chrome, edit, rows, actions, value, limit, error } = useBlock(props);

const readMore = computed(() => readMoreOf(session.model!, props.block.uid));

function add() {
	let added = "";
	edit((model) => {
		const result = addReadMore(model, props.block.uid, {
			title: chrome.value.readMoreTitle,
			text: chrome.value.readMoreText,
		});
		added = result.uid;
		return result.model;
	});
	if (added) rows.reveal(added, null);
}
</script>

<template>
	<CountedInput
		multiline
		data-main-field
		:label="chrome.labelLabel"
		:model-value="value('label')"
		:limit="limit('label')"
		:error="error('label')"
		@update:model-value="(next) => actions.setText(block, next)"
	/>
	<div class="flex flex-col gap-1.5">
		<p class="text-sm leading-tighter text-ink-gray-6">
			{{ chrome.readMoreLabel }} <span class="text-ink-gray-5">· {{ chrome.optional }}</span>
		</p>
		<div v-if="readMore" class="flex gap-2">
			<Button :label="chrome.editReadMore" @click="rows.reveal(readMore.uid, null)" />
			<Button
				v-if="!session.readOnly"
				:label="chrome.deleteLink"
				@click="edit((model) => removeReadMore(model, block.uid))"
			/>
		</div>
		<div v-else-if="!session.readOnly">
			<Button icon-left="lucide-plus" :label="chrome.addReadMore" @click="add" />
		</div>
	</div>
</template>
