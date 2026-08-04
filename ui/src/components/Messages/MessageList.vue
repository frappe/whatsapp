<script setup lang="ts">
import { Button } from "frappe-ui";
import MessageBubble from "./MessageBubble.vue";
import ReactionPicker, { REACTION_EMOJIS } from "./ReactionPicker.vue";
import ReactIcon from "./icons/ReactIcon.vue";
import type { MessageListProps, ReactPayload, WhatsAppMessage } from "./types";

withDefaults(defineProps<MessageListProps>(), {
	messages: () => [],
	senderName: "Contact",
	youLabel: "You",
	reactedByLabel: "Reacted by",
	replyLabel: "Reply",
	failedMessageLabel: "Failed to send message",
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
		<div
			v-for="message in messages"
			:key="message.name"
			class="activity group flex gap-2"
			:class="[
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
							<ReactIcon class="text-ink-gray-3" />
						</template>
					</Button>
				</ReactionPicker>
			</div>
		</div>
	</div>
</template>
