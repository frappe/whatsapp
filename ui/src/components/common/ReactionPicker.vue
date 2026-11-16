<script lang="ts">
/** Fixed by design — there is no emoji search, and callers share this list. */
export const REACTION_EMOJIS: string[] = ["👍", "❤️", "😂", "😮", "😢", "🙏"];
</script>

<script setup lang="ts">
import { Button, Popover } from "frappe-ui";
import type { ReactionPickerProps } from "./types";

const props = withDefaults(defineProps<ReactionPickerProps>(), {
	emojis: () => REACTION_EMOJIS,
});

const emit = defineEmits<{
	/** the emoji picked, or "" when the current reaction was picked again to remove it */
	select: [emoji: string];
}>();

function choose(emoji: string, close: () => void) {
	emit("select", emoji == props.selected ? "" : emoji);
	close();
}
</script>

<template>
	<Popover bare>
		<template #trigger="slotProps">
			<!-- caller supplies its own trigger; the icon button is only the fallback -->
			<slot v-bind="slotProps">
				<Button variant="ghost" aria-label="React">
					<template #icon>
						<span
							class="lucide-smile-plus size-4 text-ink-gray-7"
							aria-hidden="true"
						/>
					</template>
				</Button>
			</slot>
		</template>
		<template #default="{ close }">
			<div
				class="flex items-center justify-center gap-1 rounded-full border border-outline-gray-1 bg-surface-elevation-2 px-2 py-1 shadow-md"
			>
				<!-- a bare emoji has no accessible name, so each button gets one -->
				<Button
					v-for="emoji in emojis"
					:key="emoji"
					variant="ghost"
					class="rounded-full"
					:class="{ '!bg-surface-gray-3': emoji == selected }"
					:aria-label="`React with ${emoji}`"
					:aria-pressed="emoji == selected"
					@click="choose(emoji, close)"
				>
					<span class="text-xl leading-none">{{ emoji }}</span>
				</Button>
			</div>
		</template>
	</Popover>
</template>
