<script setup lang="ts">
import { computed } from "vue";
import { Badge, Button, Select, TextInput, Tooltip } from "frappe-ui";
import ConditionEditor from "./ConditionEditor.vue";
import ConfirmDeleteButton from "../common/ConfirmDeleteButton.vue";
import { Link } from "@framework/ui/components/Link";
import ResponseMappings from "./ResponseMappings.vue";
import { actionSummary, isStaleSource, RESPONSE_ACTION_KINDS } from "./flowButton";
import { format } from "./flowChrome";
import type { FlowButtonChrome } from "./flowChrome";
import type { FlowOutline, ResponseAction, ResponseActionKind, TemplateController } from "./types";

// Edits its action in place and reports `change`; the editor serializes the whole list.
const props = defineProps<{
	controller: TemplateController;
	chrome: FlowButtonChrome;
	action: ResponseAction;
	outline: FlowOutline | undefined;
	expanded: boolean;
	disabled: boolean;
}>();

const emit = defineEmits<{ toggle: []; remove: []; change: [] }>();

const referenceDoctype = computed(() => props.controller.doc.reference_doctype);
const isCreate = computed(() => props.action.action === "Create Document");
const summary = computed(() => actionSummary(props.action, referenceDoctype.value, props.chrome));
const condition = computed(() => props.action.condition?.trim() ?? "");
const hasStale = computed(() =>
	props.action.fields.some((field) => isStaleSource(field.source, props.outline))
);

const kindOptions = computed(() =>
	RESPONSE_ACTION_KINDS.map((kind) => ({
		value: kind,
		label:
			kind === "Create Document"
				? props.chrome.createDocument
				: props.chrome.updateReference,
	}))
);

const CREATE_FILTERS = { istable: 0, issingle: 0 };

// Target fields belong to one DocType, so a new target leaves the old field names behind.
function setKind(kind: ResponseActionKind) {
	if (kind === props.action.action) return;
	props.action.action = kind;
	clearTargets();
}

function setDoctype(doctype: string | number | null) {
	props.action.doctype = doctype == null ? "" : String(doctype);
	clearTargets();
}

function clearTargets() {
	for (const field of props.action.fields) field.target_field = "";
	emit("change");
}

function setCondition(condition: string) {
	props.action.condition = condition;
	emit("change");
}
</script>

<template>
	<li class="flex flex-col">
		<div class="flex h-9 items-center gap-2">
			<button
				type="button"
				class="flex h-full min-w-0 flex-1 items-center gap-2 rounded-2 text-left text-base text-ink-gray-8 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				:aria-expanded="expanded"
				@click="emit('toggle')"
			>
				<span
					class="lucide-chevron-right size-4 shrink-0 text-ink-gray-6 transition-transform duration-200"
					:class="{ 'rotate-90': expanded }"
					aria-hidden="true"
				/>
				<span class="min-w-0 truncate">{{ summary.title }}</span>
				<span v-if="summary.fields" class="shrink-0 text-ink-gray-5">{{ summary.fields }}</span>
				<Badge
					v-if="condition"
					class="min-w-0 max-w-72"
					variant="subtle"
					theme="gray"
					:title="format(chrome.whenSummary, condition)"
				>
					<span class="truncate font-mono">{{ condition }}</span>
				</Badge>
			</button>
			<span class="flex w-4 shrink-0 justify-center">
				<Tooltip v-if="hasStale" :text="chrome.hasStaleSource">
					<span
						class="lucide-triangle-alert size-4 text-ink-amber-7"
						role="img"
						:aria-label="chrome.hasStaleSource"
					/>
				</Tooltip>
			</span>
			<ConfirmDeleteButton
				class="shrink-0"
				:label="chrome.removeAction"
				:confirm-label="chrome.confirmRemove"
				:disabled="disabled"
				@confirm="emit('remove')"
			/>
		</div>

		<div class="expander" :class="{ open: expanded }">
			<div class="min-h-0 overflow-hidden" :inert="!expanded || undefined">
				<div class="flex flex-col gap-4 pb-5 pt-2">
					<div class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_1.75rem] gap-x-3">
						<Select
							:label="chrome.kindLabel"
							:model-value="action.action"
							:options="kindOptions"
							:disabled="disabled"
							@update:model-value="(value) => setKind(value as ResponseActionKind)"
						/>
						<Link
							v-if="isCreate"
							:label="chrome.doctypeLabel"
							doctype="DocType"
							:filters="CREATE_FILTERS"
							:model-value="action.doctype || null"
							:disabled="disabled"
							placeholder=""
							@update:model-value="setDoctype"
						/>
						<TextInput
							v-else
							:label="chrome.doctypeLabel"
							:model-value="referenceDoctype ?? ''"
							disabled
						/>
					</div>
					<div class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_1.75rem] gap-x-3">
						<ConditionEditor
							class="col-span-2"
							:model-value="action.condition ?? ''"
							:chrome="chrome"
							:outline="outline"
							:doc-fields="controller.fieldOptions"
							:disabled="disabled"
							@update:model-value="setCondition"
						/>
					</div>
					<ResponseMappings
						:controller="controller"
						:chrome="chrome"
						:action="action"
						:outline="outline"
						:disabled="disabled"
						@change="emit('change')"
					/>
				</div>
			</div>
		</div>
	</li>
</template>

<style scoped>
/* Animates to the content's own height, with nothing measured in script. */
.expander {
	display: grid;
	grid-template-rows: 0fr;
	opacity: 0;
	transition: grid-template-rows 200ms ease-out, opacity 150ms ease-out;
}
.expander.open {
	grid-template-rows: 1fr;
	opacity: 1;
}
</style>
