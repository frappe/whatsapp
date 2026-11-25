<script setup lang="ts">
import { ref } from "vue";
import { useBuilder } from "../context";

/**
 * The sheet's title bar: ✕ (or ← once there is a way back), the title and ⋮. The progress lane
 * is always there, so turning Interactive mode on moves nothing.
 */
const props = defineProps<{ title: string; back?: boolean; progress?: number | null }>();
const emit = defineEmits<{ back: [] }>();

const { chrome } = useBuilder();
const menu = ref(false);

function leading() {
	if (props.back) emit("back");
}
</script>

<template>
	<div class="relative shrink-0 border-b border-[var(--wa-divider)]">
		<div class="grid h-11 grid-cols-[3.5rem_1fr_3.5rem] items-center px-1">
			<button
				type="button"
				class="flex h-8 items-center justify-start px-2 text-[var(--wa-ink)]"
				:aria-label="back ? chrome.phoneBack : chrome.phoneClose"
				@click="leading"
			>
				<span
					class="size-[18px]"
					:class="back ? 'lucide-arrow-left' : 'lucide-x'"
					aria-hidden="true"
				/>
			</button>
			<p class="truncate text-center text-[13px] font-medium text-[var(--wa-ink)]">
				{{ title }}
			</p>
			<button
				type="button"
				class="flex h-8 items-center justify-end px-2"
				:aria-label="chrome.phoneMore"
				:aria-expanded="menu"
				@click="menu = !menu"
			>
				<span
					class="lucide-ellipsis-vertical size-[18px] text-[var(--wa-ink)]"
					aria-hidden="true"
				/>
			</button>
		</div>
		<div
			class="mx-3 mb-1.5 h-[3px] overflow-hidden rounded-full"
			:class="progress != null && 'bg-[var(--wa-divider)]'"
		>
			<div
				v-if="progress != null"
				class="h-full rounded-full bg-[var(--wa-accent)] transition-[width] duration-[250ms] [transition-timing-function:cubic-bezier(.22,1,.36,1)]"
				:style="{ width: `${progress * 100}%` }"
			/>
		</div>
		<template v-if="menu">
			<div class="fixed inset-0 z-10" @click="menu = false" />
			<ul
				class="absolute right-2 top-9 z-20 w-36 rounded-[8px] bg-[var(--wa-card)] py-1 text-[13px] text-[var(--wa-ink)] shadow-lg"
				role="menu"
			>
				<li role="menuitem" class="px-4 py-2">{{ chrome.phoneHelp }}</li>
				<li role="menuitem" aria-disabled="true" class="px-4 py-2 text-[var(--wa-ink-3)]">
					{{ chrome.phoneReport }}
				</li>
			</ul>
		</template>
	</div>
</template>
