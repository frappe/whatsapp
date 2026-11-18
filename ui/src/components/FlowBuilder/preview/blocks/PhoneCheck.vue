<script setup lang="ts">
/** WhatsApp's radio and checkbox marks. */
defineProps<{ shape: "round" | "square"; on: boolean }>();
</script>

<template>
	<span
		class="flex size-[18px] shrink-0 items-center justify-center border-2 transition-colors duration-150"
		:class="[
			shape === 'round' ? 'rounded-full' : 'rounded-[3px]',
			on ? 'border-[var(--wa-accent)]' : 'border-[var(--wa-ink-2)]',
			on && shape === 'square' ? 'bg-[var(--wa-accent)]' : '',
		]"
		aria-hidden="true"
	>
		<span v-if="on && shape === 'round'" class="size-2 rounded-full bg-[var(--wa-accent)]" />
		<span v-else-if="on" class="lucide-check size-3 text-[var(--wa-accent-ink)]" />
	</span>
</template>
