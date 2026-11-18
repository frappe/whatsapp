<script setup lang="ts">
import { computed, ref } from "vue";
import { Button, Dialog } from "frappe-ui";
import { useBuilder } from "../context";
import JsonTab from "../builder/JsonTab.vue";

/** Edit JSON from ⚙: the edits apply on Apply; a parse error keeps the dialog open at its line. */
const open = defineModel<boolean>("open", { required: true });
const { session, chrome } = useBuilder();
const editor = ref<InstanceType<typeof JsonTab>>();
const editable = computed(() => !session.readOnly);

const applying = ref(false);

/** Applied JSON is saved at once, so the dialog closes on a saved Flow. */
async function apply() {
	if (!editor.value?.apply()) return;
	applying.value = true;
	await session.flush();
	applying.value = false;
	open.value = false;
}
</script>

<template>
	<Dialog v-model:open="open" size="4xl" :title="chrome.editJson">
		<div class="-mx-5 flex h-[60vh] min-h-0 flex-col border-y border-outline-gray-1">
			<JsonTab v-if="open" ref="editor" />
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button :label="editable ? chrome.cancel : chrome.close" @click="open = false" />
				<Button
					v-if="editable"
					variant="solid"
					:label="chrome.apply"
					:loading="applying"
					@click="apply"
				/>
			</div>
		</template>
	</Dialog>
</template>
