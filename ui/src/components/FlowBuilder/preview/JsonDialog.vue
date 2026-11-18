<script setup lang="ts">
import { computed, ref } from "vue";
import { Dialog } from "frappe-ui";
import { useBuilder } from "../context";
import JsonTab from "../builder/JsonTab.vue";

/** Edit JSON from ⚙: the edits apply on Apply; a parse error keeps the dialog open at its line. */
const open = defineModel<boolean>("open", { required: true });
const { session, chrome } = useBuilder();
const editor = ref<InstanceType<typeof JsonTab>>();

const actions = computed(() =>
	session.readOnly
		? [{ label: chrome.value.close }]
		: [
				{ label: chrome.value.cancel },
				{ label: chrome.value.apply, variant: "solid" as const, onClick: apply },
		  ]
);

/** Applied JSON is saved at once, so the dialog closes on a saved Flow. */
async function apply() {
	if (!editor.value?.apply()) return;
	await session.flush();
	open.value = false;
}
</script>

<template>
	<Dialog v-model:open="open" size="4xl" :title="chrome.editJson" :actions="actions">
		<div class="-mx-5 flex h-[60vh] min-h-0 flex-col border-y border-outline-gray-1">
			<JsonTab v-if="open" ref="editor" />
		</div>
	</Dialog>
</template>
