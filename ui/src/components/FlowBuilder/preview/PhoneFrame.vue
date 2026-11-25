<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { Block, FlowModel } from "../model";
import type { PreviewSettings } from "../types";
import type { PreviewRun } from "./interactive";
import { providePhone } from "./phone";
import { phoneStyle } from "./phoneTokens";
import PhoneSheet from "./PhoneSheet.vue";
import SentChat from "./SentChat.vue";

/**
 * The phone: WhatsApp's chat dimmed behind a Flow's sheet. Its size never changes; screens
 * cross-fade inside it, and edits to the shown screen patch in place.
 */
const props = defineProps<{
	model: FlowModel;
	run: PreviewRun;
	settings: PreviewSettings;
	highlight: string | null;
}>();
const emit = defineEmits<{ pick: [blockUid: string] }>();

const sheetUid = ref<string | null>(null);
const screen = computed(() => props.run.screen);

providePhone({
	get model() {
		return props.model;
	},
	get screen() {
		return screen.value!;
	},
	get run() {
		return props.run;
	},
	get settings() {
		return props.settings;
	},
	get highlight() {
		return props.highlight;
	},
	get sheet(): Block | null {
		return screen.value?.blocks.find((block) => block.uid === sheetUid.value) ?? null;
	},
	openSheet: (block: Block) => (sheetUid.value = block.uid),
	closeSheet: () => (sheetUid.value = null),
	pick: (uid: string) => emit("pick", uid),
});

watch(
	() => screen.value?.uid,
	() => (sheetUid.value = null)
);

const view = computed(() => (props.run.sent ? "sent" : screen.value?.uid ?? "none"));
</script>

<template>
	<div
		class="flex h-[540px] max-h-full w-[326px] max-w-full shrink-0 flex-col rounded-[24px] bg-[var(--wa-bezel)] p-1.5 shadow-lg transition-colors duration-150"
		:style="phoneStyle(settings)"
		:data-theme="settings.theme"
	>
		<div
			class="relative grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] grid-rows-[minmax(0,1fr)] overflow-hidden rounded-[18px] bg-[var(--wa-scrim)] [font-family:Roboto,Inter,system-ui,sans-serif]"
		>
			<Transition name="fb-swap">
				<div v-if="view === 'sent'" key="sent" class="relative [grid-area:1/1]">
					<SentChat @restart="run.restart()" />
				</div>
				<div v-else-if="screen" :key="view" class="flex min-h-0 flex-col [grid-area:1/1]">
					<div class="flex h-7 shrink-0 items-end px-3" aria-hidden="true">
						<span
							class="size-6 translate-y-2 rounded-full bg-[var(--wa-avatar)] opacity-60"
						/>
					</div>
					<PhoneSheet />
				</div>
			</Transition>
		</div>
	</div>
</template>

<style>
.fb-swap-enter-active,
.fb-swap-leave-active {
	transition: opacity 150ms cubic-bezier(0.4, 0, 0.2, 1);
}
.fb-swap-enter-from,
.fb-swap-leave-to {
	opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
	.fb-swap-enter-active,
	.fb-swap-leave-active {
		transition: none;
	}
}
</style>
