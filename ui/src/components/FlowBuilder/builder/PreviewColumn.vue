<script setup lang="ts">
import { computed } from "vue";
import { useBuilder } from "../context";
import PhoneFrame from "../preview/PhoneFrame.vue";
import { usePreview } from "../preview/usePreview";

/** In Interactive mode the preview runs through the Flow and the left column follows it. */
const props = defineProps<{ highlight: string | null }>();
const emit = defineEmits<{ pick: [blockUid: string] }>();

const { session, chrome, rows } = useBuilder();
const { shown, run } = usePreview(session, rows);
const highlight = computed(() => (session.preview.interactive ? null : props.highlight));
</script>

<template>
	<section class="flex min-h-0 flex-col bg-surface-base" :aria-label="chrome.preview">
		<div class="flex h-12 shrink-0 items-center gap-2 px-5">
			<h2 class="text-base-medium text-ink-gray-8">{{ chrome.preview }}</h2>
			<div class="flex-1" />
			<slot name="toolbar" />
		</div>
		<div class="flex min-h-0 flex-1 items-center justify-center overflow-hidden p-5">
			<PhoneFrame
				:model="shown"
				:run="run"
				:settings="session.preview"
				:highlight="highlight"
				@pick="(uid) => emit('pick', uid)"
			/>
		</div>
		<p
			class="flex h-10 shrink-0 items-center gap-1.5 border-t border-outline-gray-1 px-5 text-sm text-ink-gray-5"
		>
			<span class="lucide-info size-3.5" aria-hidden="true" />
			{{ chrome.deviceNote }}
		</p>
	</section>
</template>
