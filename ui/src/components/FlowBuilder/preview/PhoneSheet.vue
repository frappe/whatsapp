<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { journeyScreens } from "../model";
import { useBuilder } from "../context";
import { screenTitle } from "../builder/describe";
import { usePhone } from "./phone";
import DropdownSheet from "./DropdownSheet.vue";
import PhoneBlock from "./PhoneBlock.vue";
import PhoneHeader from "./PhoneHeader.vue";

/** One screen as WhatsApp's bottom sheet: title bar, the components (scrolling), the button. */
const { chrome } = useBuilder();
const phone = usePhone();

const body = ref<HTMLElement>();

const interactive = computed(() => phone.settings.interactive);
const footer = computed(() => phone.screen.footer?.component);
const firstOnJourney = computed(() => journeyScreens(phone.model)[0]?.uid === phone.screen.uid);
const back = computed(() => (interactive.value ? phone.run.canGoBack : !firstOnJourney.value));
const progress = computed(() => {
	if (!interactive.value) return null;
	const { step, total } = phone.run.progress;
	return total ? step / total : null;
});
const ready = computed(() => interactive.value && phone.run.canContinue);

watch(
	() => phone.highlight,
	async (uid) => {
		if (!uid || interactive.value) return;
		await nextTick();
		scrollToBlock(uid);
	}
);

function scrollToBlock(uid: string) {
	const element = body.value?.querySelector<HTMLElement>(`[data-block="${CSS.escape(uid)}"]`);
	if (!element || !body.value) return;
	const box = element.getBoundingClientRect();
	const view = body.value.getBoundingClientRect();
	if (box.top < view.top || box.bottom > view.bottom)
		body.value.scrollBy({ top: box.top - view.top - 16, behavior: "smooth" });
}
</script>

<template>
	<div
		class="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-t-[14px] bg-[var(--wa-sheet)]"
	>
		<PhoneHeader
			:title="phone.text(screenTitle(phone.screen, phone.model, chrome))"
			:back="back"
			:progress="progress"
			@back="interactive && phone.run.back()"
		/>
		<div
			ref="body"
			class="fb-phone-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4"
		>
			<div class="flex flex-col gap-4">
				<PhoneBlock v-for="block in phone.screen.blocks" :key="block.uid" :block="block" />
			</div>
		</div>
		<div class="flex shrink-0 flex-col items-center gap-2 px-3 pb-2 pt-2">
			<div
				v-if="footer && (footer['left-caption'] || footer['right-caption'])"
				class="flex w-full justify-between px-1 text-[11px] text-[var(--wa-ink-2)]"
			>
				<span>{{ phone.text(footer["left-caption"]) }}</span>
				<span>{{ phone.text(footer["right-caption"]) }}</span>
			</div>
			<button
				v-if="footer"
				type="button"
				class="h-9 w-full truncate rounded-full px-4 text-[13px] font-semibold transition-[background-color,color,transform] duration-150 active:scale-[0.97]"
				:class="[
					ready
						? 'bg-[var(--wa-accent)] text-[var(--wa-accent-ink)]'
						: 'bg-[var(--wa-button-off)] text-[var(--wa-button-off-ink)]',
					!ready && 'pointer-events-none',
				]"
				:aria-disabled="!ready"
				@click="phone.run.continue()"
			>
				{{ phone.text(footer.label) }}
			</button>
			<p v-if="footer?.['center-caption']" class="text-[11px] text-[var(--wa-ink-2)]">
				{{ phone.text(footer["center-caption"]) }}
			</p>
			<p class="text-[10px] text-[var(--wa-ink-2)]">
				{{ chrome.phoneManaged }}
				<span class="font-medium text-[var(--wa-link)]">{{ chrome.phoneLearnMore }}</span>
			</p>
		</div>
		<Transition name="fb-sheet">
			<DropdownSheet
				v-if="phone.sheet"
				:key="phone.sheet.uid"
				:block="phone.sheet"
				@close="phone.closeSheet()"
			/>
		</Transition>
	</div>
</template>

<style>
.fb-phone-scroll {
	scrollbar-width: thin;
	scrollbar-color: var(--wa-field) transparent;
}
.fb-sheet-enter-active,
.fb-sheet-leave-active {
	transition: transform 200ms cubic-bezier(0.23, 1, 0.32, 1),
		opacity 200ms cubic-bezier(0.23, 1, 0.32, 1);
}
.fb-sheet-enter-from,
.fb-sheet-leave-to {
	transform: translateX(16px);
	opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
	.fb-sheet-enter-active,
	.fb-sheet-leave-active {
		transition: none;
	}
}
</style>
