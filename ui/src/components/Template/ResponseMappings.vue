<script setup lang="ts">
import { computed } from "vue";
import { Button, Combobox } from "frappe-ui";
import type { ComboboxGroupedOption } from "frappe-ui";
import FieldPicker from "./FieldPicker.vue";
import { actionTarget, isStaleSource, MESSAGE_SOURCES, sourceType } from "./flowButton";
import type { FlowButtonChrome } from "./flowChrome";
import type { FlowOutline, ResponseAction, ResponseMapping, TemplateController } from "./types";

const props = defineProps<{
	controller: TemplateController;
	chrome: FlowButtonChrome;
	action: ResponseAction;
	outline: FlowOutline | undefined;
	disabled: boolean;
}>();

const emit = defineEmits<{ change: [] }>();

const target = computed(() => actionTarget(props.action, props.controller.doc.reference_doctype));

// A saved source the Flow no longer sends stays listed, so its line still names it.
const sourceOptions = computed<ComboboxGroupedOption[]>(() => {
	const answers = (props.outline?.answers ?? []).map((answer) => ({
		value: answer.key,
		label: answer.label || answer.key,
		description: answer.key,
	}));
	const known = new Set([...answers.map((answer) => answer.value), ...MESSAGE_SOURCES]);
	for (const { source } of props.action.fields) {
		if (source && !known.has(source))
			answers.push({ value: source, label: source, description: "" });
	}
	const message = MESSAGE_SOURCES.map((source) => ({
		value: source,
		label: props.chrome[source],
	}));
	return [
		...(answers.length ? [{ group: props.chrome.answersGroup, options: answers }] : []),
		{ group: props.chrome.messageGroup, options: message },
	];
});

function targetOptions(field: ResponseMapping) {
	return props.controller.mappableFields(target.value, sourceType(field.source, props.outline));
}

function setSource(field: ResponseMapping, source: string) {
	if (source === field.source) return;
	field.source = source;
	field.target_field = "";
	emit("change");
}

function setTarget(field: ResponseMapping, targetField: string) {
	field.target_field = targetField;
	emit("change");
}

function add() {
	props.action.fields.push({ source: "", target_field: "" });
	emit("change");
}

function remove(index: number) {
	props.action.fields.splice(index, 1);
	emit("change");
}
</script>

<template>
	<div class="flex flex-col gap-2">
		<div
			v-if="action.fields.length"
			class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_1.75rem] gap-x-3 text-sm text-ink-gray-6"
		>
			<span>{{ chrome.sourceLabel }}</span>
			<span>{{ chrome.targetLabel }}</span>
		</div>
		<div
			v-for="(field, index) in action.fields"
			:key="index"
			class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_1.75rem] items-center gap-x-3 gap-y-1"
		>
			<Combobox
				:model-value="field.source || null"
				:options="sourceOptions"
				:placeholder="chrome.sourcePlaceholder"
				:disabled="disabled"
				:aria-label="chrome.sourceLabel"
				open-on-click
				@update:model-value="
					(value) => setSource(field, value == null ? '' : String(value))
				"
			/>
			<FieldPicker
				:model-value="field.target_field"
				:options="targetOptions(field)"
				:placeholder="chrome.fieldPlaceholder"
				:disabled="disabled || !field.source"
				:aria-label="chrome.targetLabel"
				:error-label="chrome.loadError"
				:retry-label="chrome.retry"
				@update:model-value="(value) => setTarget(field, value)"
			/>
			<Button
				variant="ghost"
				icon="lucide-x"
				:aria-label="chrome.removeMapping"
				:disabled="disabled"
				@click="remove(index)"
			/>
			<p
				v-if="isStaleSource(field.source, outline)"
				class="col-span-2 flex items-start gap-1.5 text-p-sm text-ink-amber-7"
			>
				<span class="lucide-triangle-alert mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
				{{ chrome.staleSource }}
			</p>
		</div>
		<div>
			<Button
				variant="ghost"
				icon-left="lucide-plus"
				:label="chrome.addMapping"
				:disabled="disabled"
				@click="add"
			/>
		</div>
	</div>
</template>
