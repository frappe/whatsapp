<!-- eslint-disable vue/no-v-html -->
<script setup lang="ts">
import { computed } from "vue";
import { Badge, Dropdown, Tooltip, dayjsLocal } from "frappe-ui";
import TemplateContent from "./TemplateContent.vue";
import { formatWhatsAppMessage } from "../../utils/formatMessage";
import { contentTypeFromMime, documentMeta, documentName, hasCaption } from "../../utils/media";
import type { MessageBubbleProps, WhatsAppDirection, WhatsAppMessage } from "./types";

const props = withDefaults(defineProps<MessageBubbleProps>(), {
	senderName: "Contact",
	youLabel: "You",
	reactedByLabel: "Reacted by",
	replyLabel: "Reply",
	failedMessageLabel: "Failed to send message",
});

const emit = defineEmits<{
	reply: [message: WhatsAppMessage];
	"jump-to": [name: string];
}>();

/** No stored column: a message is a reply iff it points at another message's id. */
const isReply = computed(() => Boolean(props.message.context_message_id));

const contentType = computed(() => contentTypeFromMime(props.message.mime_type));

/** Two participants, so direction alone names every sender this bubble shows. */
function nameFor(direction?: WhatsAppDirection) {
	return direction === "Incoming" ? props.senderName : props.youLabel;
}

const messageOptions = computed(() => [
	{
		label: props.replyLabel,
		onClick: () => emit("reply", props.message),
	},
]);

function openFileInAnotherTab(url?: string) {
	if (!url) return;
	window.open(url, "_blank");
}
</script>

<template>
	<div
		:id="message.name"
		class="group/message relative min-w-[90px] max-w-[75%] rounded-md bg-surface-gray-1 text-ink-gray-9 p-1.5 pl-2 pb-5 text-base shadow-sm"
	>
		<Tooltip v-if="message.status == 'Failed'">
			<template #content>
				<!-- the reason can be a paragraph; let it wrap instead of one long line -->
				<div class="max-w-xs whitespace-normal break-words text-left">
					{{ message.error_message || failedMessageLabel }}
				</div>
			</template>
			<Badge theme="red" :label="message.status" class="absolute -top-2 right-0" />
		</Tooltip>

		<!-- reply_message/reply_to_* only: `header`/`footer` describe *this* message's template -->
		<div
			v-if="isReply"
			class="mb-1 cursor-pointer rounded border-0 border-l-4 bg-surface-gray-3 p-2 text-ink-gray-5"
			:class="
				message.reply_to_direction == 'Incoming' ? 'border-green-500' : 'border-blue-400'
			"
			@click="() => message.reply_to && emit('jump-to', message.reply_to)"
		>
			<div
				class="mb-1 text-sm-bold"
				:class="
					message.reply_to_direction == 'Incoming'
						? 'text-ink-green-5'
						: 'text-ink-blue-link'
				"
			>
				{{ nameFor(message.reply_to_direction) }}
			</div>
			<div class="flex flex-col gap-2 max-h-12 overflow-hidden">
				<div v-html="formatWhatsAppMessage(message.reply_message)" />
			</div>
		</div>

		<div
			v-if="message.status != 'Failed'"
			class="absolute -right-0.5 -top-0.5 flex cursor-pointer gap-1 rounded-full bg-surface-white pb-2 pl-2 pr-1.5 pt-1.5 opacity-0 group-hover/message:opacity-100"
			:style="{
				background:
					'radial-gradient(circle at 50% 50%, rgba(255, 255, 255, 1) 0%, rgba(255, 255, 255, 1) 35%, rgba(238, 130, 238, 0) 100%)',
			}"
		>
			<Dropdown :options="messageOptions">
				<span class="lucide-chevron-down size-4 text-ink-gray-5" aria-hidden="true" />
			</Dropdown>
		</div>

		<div
			v-if="message.reactions?.length"
			class="absolute -bottom-5 flex gap-0.5 rounded-full border bg-surface-white p-1 pb-[3px] shadow-sm"
		>
			<Tooltip
				v-for="(reaction, i) in message.reactions"
				:key="i"
				:text="`${reactedByLabel} ${nameFor(reaction.direction)}`"
			>
				<div class="flex size-4 items-center justify-center">
					{{ reaction.emoji }}
				</div>
			</Tooltip>
		</div>

		<TemplateContent
			v-if="message.is_template"
			:header="message.header"
			:body="message.template"
			:footer="message.footer"
			:buttons="message.buttons"
		/>
		<div v-else-if="contentType == 'text'" v-html="formatWhatsAppMessage(message.message)" />
		<div v-else-if="contentType == 'image'">
			<img
				:src="message.media_url"
				class="max-h-72 max-w-full cursor-pointer rounded-md object-cover"
				@click="() => openFileInAnotherTab(message.media_url)"
			/>
			<div
				v-if="hasCaption(message.message)"
				class="mt-1.5"
				v-html="formatWhatsAppMessage(message.message)"
			/>
		</div>
		<div v-else-if="contentType == 'document'" class="flex flex-col gap-1.5">
			<div
				class="flex min-w-0 cursor-pointer items-center gap-2 rounded-md"
				:class="hasCaption(message.message) ? 'bg-surface-gray-3 p-2' : ''"
				@click="() => openFileInAnotherTab(message.media_url)"
			>
				<span
					class="lucide-file-text size-10 flex-shrink-0 rounded-md text-ink-gray-4"
					aria-hidden="true"
				/>
				<div class="flex min-w-0 flex-1 flex-col">
					<div
						:title="documentName(message)"
						class="max-w-[28ch] truncate text-ink-gray-8"
					>
						{{ documentName(message) }}
					</div>
					<div v-if="documentMeta(message)" class="text-sm text-ink-gray-5">
						{{ documentMeta(message) }}
					</div>
				</div>
			</div>
			<div
				v-if="hasCaption(message.message)"
				v-html="formatWhatsAppMessage(message.message)"
			/>
		</div>
		<div v-else-if="contentType == 'audio'" class="flex items-center gap-2">
			<audio :src="message.media_url" controls class="cursor-pointer" />
		</div>
		<div v-else-if="contentType == 'video'" class="flex-col items-center gap-2">
			<video :src="message.media_url" controls class="h-40 cursor-pointer rounded-md" />
			<div
				v-if="hasCaption(message.message)"
				class="mt-1.5"
				v-html="formatWhatsAppMessage(message.message)"
			/>
		</div>

		<div
			class="absolute bottom-1 right-2 flex items-end gap-1 whitespace-nowrap text-ink-gray-5"
		>
			<!--
				dayjsLocal, not dayjs: `creation` is naive and in the site's timezone,
				so plain dayjs would read it as browser-local and shift every stamp.
			-->
			<Tooltip :text="dayjsLocal(message.creation).format('ddd, MMM D, YYYY')">
				<div class="text-2xs">
					{{ dayjsLocal(message.creation).format("hh:mm a") }}
				</div>
			</Tooltip>
			<div v-if="message.direction == 'Outgoing'">
				<span
					v-if="message.status == 'Sent'"
					class="lucide-check size-4"
					aria-hidden="true"
				/>
				<span
					v-else-if="['Read', 'Delivered'].includes(message.status || '')"
					class="lucide-check-check size-4"
					:class="{ 'text-ink-blue-2': message.status == 'Read' }"
					aria-hidden="true"
				/>
			</div>
		</div>
	</div>
</template>
