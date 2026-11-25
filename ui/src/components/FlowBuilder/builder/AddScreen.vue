<script setup lang="ts">
import { computed, ref } from "vue";
import { Button, TextInput, vFocus } from "frappe-ui";
import { addScreenInJourney } from "../model";
import { useBuilder } from "../context";
import { collapse } from "./collapse";

/** Meta's "+ Add new": an inline name and Add. Enter adds too. */
const emit = defineEmits<{ added: [uid: string] }>();
const { chrome, edit } = useBuilder();

const open = ref(false);
const name = ref("");
const ready = computed(() => !!name.value.trim());

function add() {
	if (!ready.value) return;
	let uid = "";
	edit((model) => {
		const added = addScreenInJourney(model, { title: name.value.trim() });
		uid = added.uid;
		return added.model;
	});
	name.value = "";
	open.value = false;
	if (uid) emit("added", uid);
}
</script>

<template>
	<div class="flex flex-col">
		<div class="ps-1">
			<Button
				variant="ghost"
				icon-left="lucide-plus"
				:label="chrome.addNew"
				:aria-expanded="open"
				@click="open = !open"
			/>
		</div>
		<Transition :css="false" @enter="collapse.onEnter" @leave="collapse.onLeave">
			<div v-if="open">
				<form
					v-focus
					class="flex items-start gap-2 px-1 pt-1"
					@submit.prevent="add"
					@keydown.esc.stop="open = false"
				>
					<TextInput
						v-model="name"
						class="min-w-0 flex-1"
						:aria-label="chrome.screenName"
						:placeholder="chrome.screenName"
					/>
					<Button type="submit" :label="chrome.add" :disabled="!ready" />
				</form>
			</div>
		</Transition>
	</div>
</template>
