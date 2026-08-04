<script lang="ts">
/**
 * The reaction bar's emojis. Fixed by design — there is no picker and no emoji search, so
 * the composite and the bubble reference this list rather than each restating it.
 */
export const REACTION_EMOJIS: string[] = ["👍", "❤️", "😂", "😮", "😢", "🙏"];
</script>

<script setup lang="ts">
import { Button, Popover } from "frappe-ui";
import ReactIcon from "./icons/ReactIcon.vue";
import type { ReactionPickerProps } from "./types";

withDefaults(defineProps<ReactionPickerProps>(), {
	emojis: () => REACTION_EMOJIS,
});

const emit = defineEmits<{
	select: [emoji: string];
}>();

function choose(emoji: string, togglePopover: () => void) {
	emit("select", emoji);
	togglePopover();
}
</script>

<template>
	<Popover transition="default">
		<template #target="{ isOpen, togglePopover }">
			<!-- caller supplies its own trigger; the icon button is only the fallback -->
			<slot v-bind="{ isOpen, togglePopover }">
				<Button variant="ghost" aria-label="React" @click="togglePopover">
					<template #icon>
						<ReactIcon class="size-4 text-ink-gray-7" />
					</template>
				</Button>
			</slot>
		</template>
		<template #body="{ togglePopover }">
			<div
				class="flex items-center justify-center gap-1 rounded-full bg-surface-elevation-2 px-2 py-1 shadow-2xl ring-1 ring-black ring-opacity-5"
			>
				<!-- P12: a bare emoji has no accessible name, so each button gets one -->
				<Button
					v-for="emoji in emojis"
					:key="emoji"
					variant="ghost"
					class="rounded-full !text-xl leading-none"
					:aria-label="`React with ${emoji}`"
					@click="choose(emoji, togglePopover)"
				>
					{{ emoji }}
				</Button>
			</div>
		</template>
	</Popover>
</template>
