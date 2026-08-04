<script setup lang="ts">
import { computed, ref } from "vue";
import { LoadingIndicator } from "frappe-ui";
import MessageList from "./MessageList.vue";
import TemplateSelectorDialog from "./TemplateSelectorDialog.vue";
import { REACTION_EMOJIS } from "./ReactionPicker.vue";
import type { MessagePanelProps, ReactPayload, WhatsAppMessage } from "./types";

// Data spreads in from the controller (`v-bind="messages"`), whose verb members then arrive
// as attrs. Don't inherit those onto the root — actions are surfaced as events instead.
defineOptions({ inheritAttrs: false });

const props = withDefaults(defineProps<MessagePanelProps>(), {
	messages: () => [],
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
	sendTemplate: [templateName: string];
	"update:templatesOpen": [value: boolean];
}>();

/**
 * Controlled when the host binds `templatesOpen`, self-owned otherwise — so
 * `openTemplateSelector()` works without the host holding a boolean for us.
 */
const uncontrolledTemplatesOpen = ref(false);
const templatesVisible = computed({
	get: () => props.templatesOpen ?? uncontrolledTemplatesOpen.value,
	set: (value: boolean) => {
		uncontrolledTemplatesOpen.value = value;
		emit("update:templatesOpen", value);
	},
});

function openTemplateSelector() {
	templatesVisible.value = true;
}

defineExpose({ openTemplateSelector });
</script>

<template>
	<div class="flex h-full flex-col overflow-hidden">
		<div class="flex-1 overflow-y-auto px-3 py-4 sm:px-10">
			<!-- spinner only on first load; cached messages stay visible while revalidating -->
			<div v-if="loading && !messages.length" class="flex justify-center py-8">
				<LoadingIndicator class="size-5 text-ink-gray-5" />
			</div>
			<div
				v-else-if="!messages.length"
				class="flex h-full flex-col items-center justify-center py-8"
			>
				<span class="text-lg font-medium text-ink-gray-4">{{ emptyLabel }}</span>
			</div>
			<MessageList
				v-else
				:messages="messages"
				:sender-name="senderName"
				:you-label="youLabel"
				:reacted-by-label="reactedByLabel"
				:reply-label="replyLabel"
				:failed-message-label="failedMessageLabel"
				:reaction-emojis="reactionEmojis"
				@reply="emit('reply', $event)"
				@react="emit('react', $event)"
			/>
		</div>

		<TemplateSelectorDialog
			v-if="templates"
			v-model:open="templatesVisible"
			:templates="templates"
			@select="emit('sendTemplate', $event)"
		/>
	</div>
</template>
