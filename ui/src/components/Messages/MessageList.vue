<script setup lang="ts">
import { Button, LoadingIndicator } from "frappe-ui";
import MessageBubble from "./MessageBubble.vue";
import ReactionPicker, { REACTION_EMOJIS } from "../common/ReactionPicker.vue";
import type { MessageListProps, ReactPayload, WhatsAppMessage } from "./types";

withDefaults(defineProps<MessageListProps>(), {
	messages: () => [],
	rowClass: "",
	senderName: "Contact",
	youLabel: "You",
	reactedByLabel: "Reacted by",
	replyLabel: "Reply",
	failedMessageLabel: "Failed to send message",
	emptyLabel: "No messages yet",
	reactionEmojis: () => REACTION_EMOJIS,
});

const emit = defineEmits<{
	reply: [message: WhatsAppMessage];
	react: [payload: ReactPayload];
}>();

/** Jump to a quoted message and flash it, so the reader can find it in a long thread. */
function scrollToMessage(name: string) {
	const element = document.getElementById(name);
	if (!element) return;
	element.scrollIntoView({ behavior: "smooth" });

	element.classList.add("bg-yellow-100");
	setTimeout(() => {
		element.classList.remove("bg-yellow-100");
	}, 1000);
}
</script>

<template>
	<div>
		<!-- spinner only on first load; cached messages stay visible while revalidating -->
		<div v-if="loading && !messages.length" class="flex justify-center py-8">
			<LoadingIndicator class="size-5 text-ink-gray-5" />
		</div>
		<div v-else-if="!messages.length" class="flex flex-col items-center justify-center py-8">
			<span class="text-lg font-medium text-ink-gray-4">{{ emptyLabel }}</span>
		</div>

		<template v-else>
			<div
				v-for="message in messages"
				:key="message.name"
				class="group flex gap-2"
				:class="[
					rowClass,
					message.direction == 'Outgoing' ? 'flex-row-reverse' : '',
					message.reactions?.length ? 'mb-7' : 'mb-3',
				]"
			>
				<MessageBubble
					:message="message"
					:sender-name="senderName"
					:you-label="youLabel"
					:reacted-by-label="reactedByLabel"
					:reply-label="replyLabel"
					:failed-message-label="failedMessageLabel"
					@reply="emit('reply', $event)"
					@jump-to="scrollToMessage"
				/>
				<div
					v-if="message.status != 'Failed'"
					class="flex items-center justify-center opacity-0 transition-all ease-in group-hover:opacity-100"
				>
					<ReactionPicker
						v-slot="{ togglePopover }"
						:emojis="reactionEmojis"
						@select="emit('react', { messageName: message.name, emoji: $event })"
					>
						<Button class="rounded-full !size-6 mt-0.5" @click="togglePopover">
							<template #icon>
								<span
									class="lucide-smile-plus size-4 text-ink-gray-3"
									aria-hidden="true"
								/>
							</template>
						</Button>
					</ReactionPicker>
				</div>
			</div>
		</template>
	</div>
</template>
