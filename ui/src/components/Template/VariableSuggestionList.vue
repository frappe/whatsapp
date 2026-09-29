<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import type { VariableItem } from "./types";

// The suggestion renderer also passes `editor` and `range`.
defineOptions({ inheritAttrs: false });

const props = defineProps<{
	items: VariableItem[];
	command: (item: VariableItem) => void;
	query?: string;
}>();

const selectedIndex = ref(0);
const itemRefs = ref<HTMLButtonElement[]>([]);

watch(
	() => props.items,
	() => {
		selectedIndex.value = 0;
	}
);

function select(index: number) {
	const item = props.items[index];
	if (item) props.command(item);
}

function move(step: number) {
	const count = props.items.length;
	selectedIndex.value = (selectedIndex.value + step + count) % count;
	nextTick(() => itemRefs.value[selectedIndex.value]?.scrollIntoView({ block: "nearest" }));
}

// Returning true tells the suggestion plugin the key was consumed.
function onKeyDown({ event }: { event: KeyboardEvent }): boolean {
	if (!props.items.length) return false;
	if (event.key === "ArrowUp") {
		move(-1);
		return true;
	}
	if (event.key === "ArrowDown") {
		move(1);
		return true;
	}
	if (event.key === "Enter") {
		select(selectedIndex.value);
		return true;
	}
	return false;
}

// A literal `}}` in the template would close the mustache.
function braced(value: string) {
	return `{{${value}}}`;
}

defineExpose({ onKeyDown });
</script>

<template>
	<!-- Mounted on <body>: a host dialog disables pointer events there and dismisses on an outside
	     pointerdown or focus, so this list re-enables its own and never takes focus. -->
	<div
		v-if="items.length"
		class="pointer-events-auto max-h-72 min-w-40 overflow-y-auto rounded-lg border border-outline-gray-2 bg-surface-elevation-2 p-1 text-base shadow-2xl"
		@pointerdown.stop
	>
		<button
			v-for="(item, index) in items"
			:key="item.value"
			:ref="(el) => (itemRefs[index] = el as HTMLButtonElement)"
			type="button"
			tabindex="-1"
			class="flex w-full items-center whitespace-nowrap rounded px-2 py-1.5 text-sm text-ink-gray-8"
			:class="{ 'bg-surface-gray-2': index === selectedIndex }"
			@mousedown.prevent
			@click.stop.prevent="select(index)"
			@mouseover="selectedIndex = index"
		>
			{{ braced(item.value) }}
		</button>
	</div>
</template>
