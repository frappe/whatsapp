<script setup lang="ts">
import { computed } from "vue";
import { format } from "../../chrome";
import { useBuilder } from "../../context";

/**
 * WhatsApp's text field: outlined, with a floating label that sits inside until there is a value,
 * then moves up.
 */
const props = defineProps<{
	label: string;
	required: boolean;
	filled: boolean;
	helper?: string;
	tall?: boolean;
}>();

const { chrome } = useBuilder();
const label = computed(() =>
	props.required ? props.label : format(chrome.value.phoneOptional, props.label)
);
</script>

<template>
	<div class="flex flex-col gap-1">
		<label
			class="group relative flex cursor-text px-3 transition-colors duration-150"
			:class="[
				tall ? 'min-h-[84px] items-start pt-3' : 'h-11 items-center',
				'rounded-[6px] border border-[var(--wa-field)] focus-within:border-[var(--wa-accent)]',
			]"
		>
			<span
				class="pointer-events-none absolute truncate transition-all duration-150 [transition-timing-function:cubic-bezier(.4,0,.2,1)]"
				:class="
					filled
						? 'left-2 top-0 -translate-y-1/2 bg-[var(--wa-sheet)] px-1 text-[10px] text-[var(--wa-ink-2)] group-focus-within:text-[var(--wa-accent)]'
						: `left-3 text-[13px] text-[var(--wa-ink-3)] ${
								tall ? 'top-3' : 'top-1/2 -translate-y-1/2'
						  }`
				"
			>
				{{ label }}
			</span>
			<slot />
		</label>
		<div
			v-if="helper || $slots.after"
			class="flex gap-2 px-3 text-[10px] leading-[14px] text-[var(--wa-ink-2)]"
		>
			<span class="min-w-0 flex-1">{{ helper }}</span>
			<slot name="after" />
		</div>
	</div>
</template>
