<script setup lang="ts">
import { computed } from "vue";
import { Button, Checkbox, Popover } from "frappe-ui";
import type { WhatsAppFlowStatus } from "../Messages/types";
import type { FlowBuilderChrome } from "./chrome";
import { STATUS_THEME } from "./status";
import { FLOW_CATEGORIES } from "./types";
import type { FlowCategory } from "./types";

defineProps<{ chrome: FlowBuilderChrome }>();
const statuses = defineModel<WhatsAppFlowStatus[]>("statuses", { required: true });
const categories = defineModel<FlowCategory[]>("categories", { required: true });

const STATUSES = Object.keys(STATUS_THEME) as WhatsAppFlowStatus[];
const activeCount = computed(() => statuses.value.length + categories.value.length);

function toggle<T>(list: T[], value: T, on: boolean): T[] {
	return on ? [...list, value] : list.filter((item) => item !== value);
}

function clear() {
	statuses.value = [];
	categories.value = [];
}
</script>

<template>
	<Popover align="end">
		<template #trigger>
			<Button
				v-if="activeCount"
				icon-left="lucide-list-filter"
				:label="String(activeCount)"
				:aria-label="chrome.filter"
			/>
			<Button v-else icon="lucide-list-filter" :aria-label="chrome.filter" />
		</template>
		<div class="flex flex-col gap-3 p-3">
			<div class="grid grid-cols-2 gap-x-4">
				<fieldset class="flex flex-col gap-0.5">
					<legend class="px-2 pb-1 text-sm text-ink-gray-5">{{ chrome.columnStatus }}</legend>
					<Checkbox
						v-for="value in STATUSES"
						:key="value"
						padded
						:label="chrome[value]"
						:model-value="statuses.includes(value)"
						@update:model-value="(on) => (statuses = toggle(statuses, value, Boolean(on)))"
					/>
				</fieldset>
				<fieldset class="flex flex-col gap-0.5">
					<legend class="px-2 pb-1 text-sm text-ink-gray-5">
						{{ chrome.columnCategories }}
					</legend>
					<Checkbox
						v-for="value in FLOW_CATEGORIES"
						:key="value"
						padded
						:label="chrome[value] ?? value"
						:model-value="categories.includes(value)"
						@update:model-value="(on) => (categories = toggle(categories, value, Boolean(on)))"
					/>
				</fieldset>
			</div>
			<Button
				class="self-start"
				variant="ghost"
				icon-left="lucide-x"
				:label="chrome.clearFilters"
				:disabled="!activeCount"
				@click="clear"
			/>
		</div>
	</Popover>
</template>
