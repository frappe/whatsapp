<script setup lang="ts">
import { computed } from "vue";
import FieldPicker from "./FieldPicker.vue";
import type { FlowButtonChrome } from "./flowChrome";
import type { FlowInput, TemplateController } from "./types";

const props = defineProps<{
	controller: TemplateController;
	chrome: FlowButtonChrome;
	inputs: FlowInput[];
	/** The entry screen's declared keys and types; null while unknown. */
	declared: Record<string, string> | null;
	hasFlow: boolean;
	/** The outline is still loading, so the lines are the saved ones and stay disabled. */
	pending: boolean;
	disabled: boolean;
}>();

const emit = defineEmits<{ update: [inputs: FlowInput[]] }>();

const referenceDoctype = computed(() => props.controller.doc.reference_doctype);

// Until the outline says what the screen declares, the saved keys hold the lines' places.
const lines = computed(() => {
	if (!props.declared) {
		return props.inputs.map((input) => ({ ...input, type: props.pending ? "" : "unknown" }));
	}
	const saved = new Map(props.inputs.map((input) => [input.key, input.source_field]));
	return Object.entries(props.declared).map(([key, type]) => ({
		key,
		type,
		source_field: saved.get(key) ?? "",
	}));
});

const note = computed(() => {
	if (!props.hasFlow) return props.chrome.noFlowChosen;
	if (lines.value.length || props.pending) return "";
	return props.declared ? props.chrome.noInputs : props.chrome.inputsUnlisted;
});

function setSource(key: string, source_field: string) {
	emit(
		"update",
		lines.value.map((line) => ({
			key: line.key,
			source_field: line.key === key ? source_field : line.source_field,
		}))
	);
}
</script>

<template>
	<section class="flex flex-col gap-3">
		<header class="flex flex-col gap-0.5">
			<h4 class="text-sm-medium text-ink-gray-8">{{ chrome.inputsHeading }}</h4>
			<p class="truncate text-p-sm text-ink-gray-6">
				{{ referenceDoctype ? chrome.inputsHint : chrome.noReference }}
			</p>
		</header>
		<p v-if="note" class="flex h-7 items-center text-sm text-ink-gray-6">{{ note }}</p>
		<div
			v-for="line in lines"
			:key="line.key"
			class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_1.75rem] items-center gap-x-3"
		>
			<div class="flex min-w-0 items-baseline gap-2">
				<span class="truncate font-mono text-sm text-ink-gray-8" :title="line.key">{{
					line.key
				}}</span>
				<span v-if="line.type !== 'unknown'" class="shrink-0 text-sm text-ink-gray-6">{{
					line.type
				}}</span>
			</div>
			<FieldPicker
				:model-value="line.source_field"
				:options="
					pending ? null : controller.inputSourceFields(referenceDoctype, line.type)
				"
				:placeholder="chrome.fieldPlaceholder"
				:disabled="disabled || !referenceDoctype"
				:aria-label="line.key"
				:error-label="chrome.loadError"
				:retry-label="chrome.retry"
				@update:model-value="(value) => setSource(line.key, value)"
			/>
		</div>
	</section>
</template>
