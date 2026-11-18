<script setup lang="ts">
import { computed } from "vue";
import { Button, Dropdown } from "frappe-ui";
import type { Severity } from "../model";
import { useBuilder } from "../context";
import { collapse } from "./collapse";

/**
 * One "Edit content" row: `Type · summary` when closed, its editor below when open. Every lane
 * (handle, warning, actions, chevron) keeps its width on every row, so nothing shifts sideways.
 */
const props = defineProps<{
	id: string;
	title: string;
	summary?: string;
	open: boolean;
	severity: Severity | null;
	/** Handlers for the drag handle; none on Screen title and Button. */
	handle?: Record<string, unknown>;
	actions?: {
		label: string;
		icon: string;
		disabled?: boolean;
		theme?: "red";
		onClick: () => void;
	}[];
	dragging?: boolean;
	/** An Advanced block has nothing to edit here. */
	locked?: boolean;
}>();
const emit = defineEmits<{ toggle: [] }>();

const { chrome } = useBuilder();
const panelId = computed(() => `fb-panel-${props.id}`);
</script>

<template>
	<li
		:data-row="id"
		class="rounded-5 border bg-surface-base transition-[opacity,border-color] duration-150"
		:class="[
			dragging ? 'opacity-50' : '',
			open ? 'border-outline-gray-2' : 'border-outline-elevation-2',
		]"
	>
		<div
			class="flex h-9 items-center gap-0.5 rounded-5 pe-1 ps-1"
			:class="!locked && 'hover:bg-surface-gray-1'"
		>
			<span v-if="handle" class="flex w-6 shrink-0 justify-center">
				<Button
					variant="ghost"
					size="xs"
					icon="lucide-grip-vertical"
					class="cursor-grab text-ink-gray-5 active:cursor-grabbing"
					:aria-label="chrome.dragToReorder"
					v-bind="handle"
				/>
			</span>
			<button
				type="button"
				class="flex h-9 min-w-0 flex-1 items-center gap-1.5 text-left text-base"
				:class="[handle ? 'ps-1' : 'ps-2', locked && 'cursor-default']"
				:aria-expanded="locked ? undefined : open"
				:aria-controls="locked ? undefined : panelId"
				:disabled="locked"
				@click="emit('toggle')"
			>
				<span class="shrink-0 text-ink-gray-8">{{ title }}</span>
				<span
					class="min-w-0 truncate text-ink-gray-5 transition-opacity duration-150"
					:class="open || !summary ? 'opacity-0' : 'opacity-100'"
					:aria-hidden="open || !summary"
				>
					· {{ summary }}
				</span>
			</button>
			<span class="flex w-6 shrink-0 justify-center">
				<span
					v-if="severity"
					class="lucide-triangle-alert size-4"
					:class="severity === 'error' ? 'text-ink-red-5' : 'text-ink-amber-5'"
					role="img"
					:aria-label="severity === 'error' ? chrome.hasProblem : chrome.hasWarning"
				/>
			</span>
			<span class="flex w-7 shrink-0 justify-center">
				<Dropdown v-if="actions?.length" :options="actions" align="end">
					<Button
						variant="ghost"
						size="sm"
						icon="lucide-ellipsis"
						:aria-label="chrome.rowActions"
					/>
				</Dropdown>
			</span>
			<span class="flex w-7 shrink-0 justify-center">
				<Button
					v-if="!locked"
					variant="ghost"
					size="sm"
					tabindex="-1"
					aria-hidden="true"
					class="text-ink-gray-5"
					@click="emit('toggle')"
				>
					<template #icon>
						<span
							class="lucide-chevron-down size-4 transition-transform duration-200 ease-[cubic-bezier(.23,1,.32,1)] motion-reduce:transition-none"
							:class="open && 'rotate-180'"
						/>
					</template>
				</Button>
			</span>
		</div>
		<Transition :css="false" @enter="collapse.onEnter" @leave="collapse.onLeave">
			<div v-if="open" :id="panelId" role="region" :aria-label="title">
				<div class="flex flex-col gap-4 px-3 pb-3 pt-2">
					<slot />
				</div>
			</div>
		</Transition>
	</li>
</template>
