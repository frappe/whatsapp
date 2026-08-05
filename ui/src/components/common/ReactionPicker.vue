<script lang="ts">
/** Fixed by design — there is no emoji search, and callers share this list. */
export const REACTION_EMOJIS: string[] = ["👍", "❤️", "😂", "😮", "😢", "🙏"];
</script>

<script setup lang="ts">
import { Button, Popover } from "frappe-ui";
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
						<span
							class="lucide-smile-plus size-4 text-ink-gray-7"
							aria-hidden="true"
						/>
					</template>
				</Button>
			</slot>
		</template>
		<template #body="{ togglePopover }">
			<div
				class="flex items-center justify-center gap-1 rounded-full bg-surface-elevation-2 px-2 py-1 shadow-2xl ring-1 ring-black ring-opacity-5"
			>
				<!-- a bare emoji has no accessible name, so each button gets one -->
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
