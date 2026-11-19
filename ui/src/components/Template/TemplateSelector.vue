<script setup lang="ts">
import { computed, h, onMounted, ref, useTemplateRef, watch } from "vue";
import { Badge, Button, Dropdown, ErrorMessage, LoadingIndicator, TextInput } from "frappe-ui";
import TemplateContent from "../Messages/TemplateContent.vue";
import { useTemplates } from "../Messages/useTemplates";
import { serverErrorMessage } from "../../utils/serverError";
import type { WhatsAppTemplate } from "../Messages/types";
import type { TemplateSelectorProps, TemplateType } from "./types";

const CATEGORIES: TemplateType[] = ["Marketing", "Utility", "Authentication"];

const props = defineProps<TemplateSelectorProps>();
const emit = defineEmits<{ sent: [messageName: string] }>();
defineSlots<{
	/** sits right of the search and the category filter */
	actions?: () => unknown;
	/** replaces the state shown when no template is approved yet */
	empty?: () => unknown;
}>();

const templates = useTemplates({
	referenceDoctype: () => props.referenceDoctype,
	referenceDocname: () => props.referenceDocname,
	to: () => props.to,
	filters: () => props.filters,
});

const search = ref("");
const category = ref("");
const selected = ref("");
const sending = ref(false);
const sendError = ref("");
const searchInput = useTemplateRef<{ focus: () => void }>("searchInput");
const recipientHint = computed(() => (props.to ? "" : "Add a phone number to send a template."));

const searched = computed(() => {
	const query = search.value.toLowerCase();
	return templates.templates.filter((template) =>
		[template.template_label, template.template_name, template.language].some((text) =>
			text?.toLowerCase().includes(query)
		)
	);
});
const visible = computed(() =>
	searched.value.filter(
		(template) => !category.value || template.template_type === category.value
	)
);
const categoryOptions = computed(() =>
	[{ value: "", label: "All" }, ...CATEGORIES.map((value) => ({ value, label: value }))].map(
		(option) => ({
			label: option.label,
			selected: category.value === option.value,
			slots: {
				suffix: () =>
					h("span", { class: "text-sm text-ink-gray-5" }, String(count(option.value))),
			},
			onClick: () => (category.value = option.value),
		})
	)
);

function count(value: string): number {
	return searched.value.filter((template) => !value || template.template_type === value).length;
}

function label(template: WhatsAppTemplate): string {
	return template.template_label || template.template_name || template.name;
}

async function send() {
	sending.value = true;
	sendError.value = "";
	const sent = await templates.sendTemplate(selected.value);
	sending.value = false;
	if (sent) emit("sent", sent);
	else sendError.value = serverErrorMessage(templates.error) || "Could not send the template";
}

watch(selected, () => (sendError.value = ""));

onMounted(() => searchInput.value?.focus());
</script>

<template>
	<div class="flex min-h-0 flex-col gap-4">
		<div class="flex items-center gap-2">
			<TextInput
				ref="searchInput"
				v-model="search"
				class="flex-1"
				type="text"
				placeholder="Search templates"
				aria-label="Search templates"
			>
				<template #prefix>
					<span class="lucide-search size-4 text-ink-gray-4" aria-hidden="true" />
				</template>
			</TextInput>
			<Dropdown :options="categoryOptions" align="end">
				<Button :label="category || 'All'" icon-left="lucide-list-filter" />
			</Dropdown>
			<slot name="actions" />
		</div>
		<div
			v-if="templates.loading && !templates.templates.length"
			class="grid h-56 place-items-center"
		>
			<LoadingIndicator class="size-5 text-ink-gray-4" />
		</div>
		<slot v-else-if="!templates.templates.length" name="empty">
			<div class="flex h-56 flex-col items-center justify-center gap-1 text-center">
				<p class="text-base text-ink-gray-7">No approved templates</p>
				<p class="text-p-sm text-ink-gray-5">
					Templates approved by Meta for this number show up here.
				</p>
			</div>
		</slot>
		<div v-else-if="!visible.length" class="grid h-56 place-items-center">
			<p class="text-base text-ink-gray-7">No matching templates</p>
		</div>
		<div
			v-else
			class="grid max-h-[60vh] grid-cols-1 gap-3 overflow-y-auto p-0.5 sm:grid-cols-3"
		>
			<button
				v-for="template in visible"
				:key="template.name"
				type="button"
				class="flex h-56 flex-col gap-2 rounded-6 border bg-surface-base p-3 text-start transition-colors"
				:class="
					selected === template.name
						? 'border-outline-gray-4 ring-1 ring-outline-gray-4'
						: 'border-outline-gray-1 hover:border-outline-gray-3'
				"
				:aria-pressed="selected === template.name"
				@click="selected = template.name"
			>
				<span class="flex w-full items-center gap-2 border-b border-outline-gray-1 pb-2">
					<span class="truncate text-base-semibold text-ink-gray-9">{{
						label(template)
					}}</span>
					<Badge
						v-if="template.language"
						class="ms-auto shrink-0"
						theme="gray"
						variant="subtle"
						:label="template.language"
					/>
				</span>
				<TemplateContent
					class="min-h-0 w-full flex-1 overflow-hidden text-p-sm text-ink-gray-5 [mask-image:linear-gradient(to_bottom,black_80%,transparent)]"
					:header="template.header_text"
					:body="template.message"
					:footer="template.footer"
					:buttons="template.buttons"
				/>
			</button>
		</div>
		<div class="flex items-center justify-between gap-4">
			<ErrorMessage :message="sendError || recipientHint" />
			<Button
				class="ms-auto"
				variant="solid"
				label="Send"
				icon-left="lucide-send"
				:disabled="!selected || !to"
				:loading="sending"
				@click="send"
			/>
		</div>
	</div>
</template>
