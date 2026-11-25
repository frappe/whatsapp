<script setup lang="ts">
import { reactive, toRaw } from "vue";
import { Button } from "frappe-ui";
import ResponseActionRow from "./ResponseActionRow.vue";
import type { FlowButtonChrome } from "./flowChrome";
import type { FlowOutline, ResponseAction, TemplateController } from "./types";

// Rows are edited in place; `change` asks the editor to write the list back to the button.
const props = defineProps<{
	controller: TemplateController;
	chrome: FlowButtonChrome;
	actions: ResponseAction[];
	outline: FlowOutline | undefined;
	disabled: boolean;
}>();

const emit = defineEmits<{ change: [] }>();

const expanded = reactive(new WeakSet<object>());
const keys = new WeakMap<object, number>();
let nextKey = 0;

function keyOf(action: ResponseAction) {
	const raw = toRaw(action);
	if (!keys.has(raw)) keys.set(raw, nextKey++);
	return keys.get(raw)!;
}

function toggle(action: ResponseAction) {
	if (expanded.has(action)) expanded.delete(action);
	else expanded.add(action);
}

function add() {
	const action: ResponseAction = {
		action: props.controller.doc.reference_doctype ? "Update Reference" : "Create Document",
		doctype: "",
		condition: "",
		fields: [{ source: "", target_field: "" }],
	};
	props.actions.push(action);
	expanded.add(props.actions[props.actions.length - 1]);
	emit("change");
}

function remove(index: number) {
	props.actions.splice(index, 1);
	emit("change");
}
</script>

<template>
	<section class="flex flex-col gap-3">
		<header class="flex flex-col gap-0.5">
			<h4 class="text-sm-medium text-ink-gray-8">{{ chrome.actionsHeading }}</h4>
			<p class="truncate text-p-sm text-ink-gray-6">{{ chrome.actionsHint }}</p>
		</header>
		<p v-if="!actions.length" class="flex h-7 items-center text-sm text-ink-gray-6">
			{{ chrome.noActions }}
		</p>
		<TransitionGroup
			v-else
			tag="ul"
			name="action"
			class="flex flex-col divide-y divide-outline-gray-1 border-y border-outline-gray-1"
		>
			<ResponseActionRow
				v-for="(action, index) in actions"
				:key="keyOf(action)"
				:controller="controller"
				:chrome="chrome"
				:action="action"
				:outline="outline"
				:expanded="expanded.has(action)"
				:disabled="disabled"
				@toggle="toggle(action)"
				@remove="remove(index)"
				@change="emit('change')"
			/>
		</TransitionGroup>
		<div>
			<Button
				variant="subtle"
				icon-left="lucide-plus"
				:label="chrome.addAction"
				:disabled="disabled"
				@click="add"
			/>
		</div>
	</section>
</template>

<style scoped>
.action-enter-active {
	transition: opacity 150ms ease-out;
}
.action-enter-from {
	opacity: 0;
}
</style>
