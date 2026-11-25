<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Badge, Button, Combobox, FormLabel, Select } from "frappe-ui";
import FlowInputsEditor from "./FlowInputsEditor.vue";
import FlowPreviewDialog from "../FlowBuilder/preview/FlowPreviewDialog.vue";
import ResponseActionsEditor from "./ResponseActionsEditor.vue";
import { FLOW_BUTTON_CHROME } from "./flowChrome";
import { STATUS_THEME } from "../FlowBuilder/status";
import { parseActions, parseInputs, serializeActions, serializeInputs } from "./flowButton";
import type { FlowButtonEditorProps, FlowInput, TemplateButtonRow } from "./types";
import type { WhatsAppFlowStatus } from "../Messages/types";

const props = withDefaults(defineProps<FlowButtonEditorProps>(), { disabled: false });

const UNUSABLE: WhatsAppFlowStatus[] = ["Blocked", "Deprecated"];

const chrome = computed(() => ({ ...FLOW_BUTTON_CHROME, ...props.chrome }));

const flows = computed(() => props.controller.flows);
const flowOptions = computed(() =>
	(flows.value?.data ?? []).map((flow) => ({
		value: flow.name,
		label: flow.flow_name || flow.name,
		status: flow.status,
		disabled: UNUSABLE.includes(flow.status) && flow.name !== props.button.flow,
	}))
);
const flow = computed(() =>
	flows.value?.data?.find((option) => option.name === props.button.flow)
);

const outlineState = computed(() => props.controller.outline(props.button.flow));
const outline = computed(() => outlineState.value?.data);
const emptyOutline = computed(() => !!outline.value && !outline.value.screens.length);

const entryScreens = computed(() => Object.keys(outline.value?.entry_screens ?? {}));
// Without an outline the saved screen is still the button's, so it stays shown.
const screenOptions = computed(() =>
	(entryScreens.value.length || !props.button.flow_screen
		? entryScreens.value
		: [props.button.flow_screen]
	).map((id) => ({ label: outline.value?.screen_titles?.[id] || id, value: id }))
);
// An empty screen opens the Flow's first entry screen; the server fills it in on save.
const screen = computed(() => props.button.flow_screen || entryScreens.value[0] || "");
const declared = computed(() =>
	outline.value?.screens.length ? outline.value.entry_screens[screen.value] ?? {} : null
);

const previewing = ref(false);
const actionOptions = computed(() => [
	{ value: "Navigate", label: chrome.value.actionNavigate },
	{ value: "Data Exchange", label: chrome.value.actionDataExchange },
]);

const inputs = computed(() => parseInputs(props.button.flow_inputs));

// A working copy, so rows keep their identity (and their expanded state) across edits.
const actions = ref(parseActions(props.button.flow_response_actions));
let written = props.button.flow_response_actions;
watch(
	() => props.button.flow_response_actions,
	(json) => {
		if (json === written) return;
		written = json;
		actions.value = parseActions(json);
	}
);

function set(patch: Partial<TemplateButtonRow>) {
	Object.assign(props.button, patch);
}

// Inputs and screen belong to one Flow, so a new Flow starts them over.
function setFlow(name: string | number | null) {
	const value = name == null ? "" : String(name);
	if (value === props.button.flow) return;
	const next = flows.value?.data?.find((option) => option.name === value);
	set({
		flow: value,
		flow_screen: "",
		flow_inputs: "[]",
		flow_action: next?.endpoint_uri ? props.button.flow_action : "Navigate",
	});
}

function setScreen(value: string) {
	const keys = Object.keys(outline.value?.entry_screens[value] ?? {});
	const kept = inputs.value.filter((input) => keys.includes(input.key));
	set({ flow_screen: value, flow_inputs: serializeInputs(kept) });
}

function setInputs(next: FlowInput[]) {
	set({ flow_inputs: serializeInputs(next) });
}

function pick(closePicker: () => void, link: (() => void) | undefined) {
	closePicker();
	link?.();
}

function writeActions() {
	written = serializeActions(actions.value);
	set({ flow_response_actions: written });
}
</script>

<template>
	<div class="flex flex-col gap-8 text-ink-gray-8">
		<section class="flex flex-col gap-3">
			<div class="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_1.75rem] gap-x-3 gap-y-4">
				<div class="flex flex-col gap-1.5">
					<div class="flex items-center justify-between gap-2">
						<FormLabel :label="chrome.flowLabel" />
						<!-- Ghost buttons with the padding trimmed. Negative margins keep the label row as
						     tall as the screen picker's. -->
						<div class="flow-links -my-1.5 flex min-w-0 items-center gap-2">
							<Button
								v-if="flows?.error"
								variant="ghost"
								size="sm"
								:label="`${chrome.flowsError} · ${chrome.retry}`"
								@click="flows.retry()"
							/>
							<Button
								v-else-if="button.flow"
								variant="ghost"
								size="sm"
								:label="chrome.previewLabel"
								@click="previewing = true"
							/>
						</div>
					</div>
					<Combobox
						trigger="button"
						:model-value="button.flow || null"
						:options="flowOptions"
						:placeholder="chrome.flowPlaceholder"
						:disabled="disabled"
						:loading="flows?.loading && !flowOptions.length"
						:aria-label="chrome.flowLabel"
						@update:model-value="setFlow"
					>
						<template #suffix="{ open }">
							<Badge
								v-if="flow"
								class="shrink-0"
								size="sm"
								variant="subtle"
								:theme="STATUS_THEME[flow.status]"
								:label="flow.status"
							/>
							<span
								class="lucide-chevron-down size-4 shrink-0 text-ink-gray-4 transition-transform duration-200"
								:class="{ 'rotate-180': open }"
								aria-hidden="true"
							/>
						</template>
						<template #item-suffix="{ item }">
							<Badge
								size="sm"
								variant="subtle"
								:theme="STATUS_THEME[item.status as WhatsAppFlowStatus]"
								:label="item.status"
							/>
						</template>
						<template
							v-if="(onNewFlow && controller.doc.whatsapp_account) || onManageFlows"
							#footer="{ close }"
						>
							<Button
								v-if="onNewFlow && controller.doc.whatsapp_account"
								variant="ghost"
								class="w-full !justify-start"
								icon-left="lucide-plus"
								:label="chrome.newFlow"
								@click="pick(close, onNewFlow)"
							/>
							<Button
								v-if="onManageFlows"
								variant="ghost"
								class="w-full !justify-start"
								icon-left="lucide-settings-2"
								:label="chrome.manageFlows"
								@click="pick(close, onManageFlows)"
							/>
						</template>
						<template #empty>
							<div class="px-2.5 py-1.5 text-sm text-ink-gray-6">
								{{
									!controller.doc.whatsapp_account
										? chrome.noAccount
										: flows?.error
										? chrome.flowsError
										: chrome.noFlows
								}}
							</div>
						</template>
					</Combobox>
				</div>
				<Select
					:label="chrome.screenLabel"
					:model-value="screen"
					:options="screenOptions"
					:placeholder="button.flow ? chrome.screenPlaceholder : ''"
					:disabled="disabled || !entryScreens.length"
					@update:model-value="(value) => setScreen(String(value ?? ''))"
				/>
				<span />
				<Transition name="fade">
					<Select
						v-if="flow?.endpoint_uri"
						:label="chrome.actionLabel"
						:model-value="button.flow_action || 'Navigate'"
						:options="actionOptions"
						:disabled="disabled"
						@update:model-value="(value) => set({ flow_action: value as TemplateButtonRow['flow_action'] })"
					/>
				</Transition>
			</div>
			<p
				v-if="outlineState?.error"
				class="flex items-center gap-1.5 text-p-sm text-ink-gray-7"
			>
				<span
					class="lucide-circle-alert size-4 shrink-0 text-ink-red-7"
					aria-hidden="true"
				/>
				{{ chrome.outlineError }}
				<button
					type="button"
					class="font-medium text-ink-gray-8 hover:underline"
					@click="outlineState.retry()"
				>
					{{ chrome.retry }}
				</button>
			</p>
			<p v-else-if="emptyOutline" class="flex items-start gap-1.5 text-p-sm text-ink-gray-7">
				<span
					class="lucide-info mt-0.5 size-4 shrink-0 text-ink-gray-6"
					aria-hidden="true"
				/>
				{{ chrome.emptyOutline }}
			</p>
		</section>

		<FlowPreviewDialog
			v-if="button.flow"
			v-model:open="previewing"
			:flow="button.flow"
			:title="flow?.flow_name"
		/>

		<FlowInputsEditor
			:controller="controller"
			:chrome="chrome"
			:inputs="inputs"
			:declared="declared"
			:pending="!!outlineState && !outline && !outlineState.error"
			:disabled="disabled"
			@update="setInputs"
		/>

		<ResponseActionsEditor
			:controller="controller"
			:chrome="chrome"
			:actions="actions"
			:outline="outline"
			:disabled="disabled"
			@change="writeActions"
		/>
	</div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
	transition: opacity 150ms ease-out;
}
.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}
.flow-links :deep(button) {
	padding-inline: 0.25rem;
}
</style>
