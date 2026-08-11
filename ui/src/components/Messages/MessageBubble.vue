<!-- eslint-disable vue/no-v-html -->
<script setup lang="ts">
import { computed } from "vue";
import { Button, LoadingIndicator, Tooltip, dayjsLocal } from "frappe-ui";
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

const creation = computed(() => dayjsLocal(props.message.creation));

/** Two participants, so direction alone names every sender this bubble shows. */
function nameFor(direction?: WhatsAppDirection) {
	return direction === "Incoming" ? props.senderName : props.youLabel;
}
</script>

<template>
	<!--
		Width is capped here rather than on the coloured body, and this column is sized by its
		content, so the row never stretches it and the cap stays relative to the row.

		`data-direction` sits here too, so the footer below the body can read it; a group
		variant only reaches descendants.
	-->
	<div
		class="group/bubble flex min-w-0 max-w-[80%] flex-col gap-1 data-[direction=Outgoing]:items-end"
		:data-direction="message.direction"
	>
		<div
			class="flex w-full items-center gap-1 group-data-[direction=Outgoing]/bubble:flex-row-reverse"
		>
			<!-- no `overflow-hidden`: it would clip the reaction chip that hangs below the edge,
			     and `break-words` already contains a long unbroken URL -->
			<div
				:id="message.name"
				class="relative w-fit min-w-0 max-w-full break-words rounded-lg bg-surface-gray-1 px-2.5 py-1.5 text-p-base text-ink-gray-9 shadow-[inset_0_0_0.25px_0.25px_rgba(0,0,0,0.03)] has-[[data-slot=reactions]]:mb-3 group-data-[direction=Outgoing]/bubble:bg-surface-gray-2"
			>
				<!-- reply_message/reply_to_* only: `header`/`footer` describe *this* message's template -->
				<button
					v-if="isReply"
					type="button"
					class="mb-1 block w-full rounded border-l-2 border-outline-gray-3 bg-surface-gray-4 p-2 text-left text-ink-gray-7"
					@click="() => message.reply_to && emit('jump-to', message.reply_to)"
				>
					<div class="mb-0.5 text-sm text-ink-gray-6">
						{{ nameFor(message.reply_to_direction) }}
					</div>
					<!-- clamped, not cropped: a fixed max-height slices the last line in half -->
					<div
						class="line-clamp-2"
						v-html="formatWhatsAppMessage(message.reply_message)"
					/>
				</button>

				<TemplateContent
					v-if="message.is_template"
					:header="message.header"
					:body="message.template"
					:footer="message.footer"
					:buttons="message.buttons"
				/>
				<div
					v-else-if="contentType == 'text'"
					v-html="formatWhatsAppMessage(message.message)"
				/>
				<div v-else-if="contentType == 'image'">
					<a :href="message.media_url" target="_blank" rel="noopener noreferrer">
						<img
							:src="message.media_url"
							:alt="documentName(message, 'Image')"
							class="max-h-72 max-w-full rounded object-contain"
						/>
					</a>
					<div
						v-if="hasCaption(message.message)"
						class="mt-1.5"
						v-html="formatWhatsAppMessage(message.message)"
					/>
				</div>
				<div v-else-if="contentType == 'document'" class="flex flex-col gap-1.5">
					<a
						:href="message.media_url"
						target="_blank"
						rel="noopener noreferrer"
						class="flex min-w-0 items-center gap-2 rounded-md"
						:class="hasCaption(message.message) ? 'bg-surface-gray-4 p-2' : ''"
					>
						<span
							class="lucide-file-text size-10 flex-shrink-0 rounded-md text-ink-gray-4"
							aria-hidden="true"
						/>
						<div class="flex min-w-0 flex-1 flex-col">
							<div :title="documentName(message)" class="truncate text-ink-gray-8">
								{{ documentName(message) }}
							</div>
							<div v-if="documentMeta(message)" class="text-sm text-ink-gray-6">
								{{ documentMeta(message) }}
							</div>
						</div>
					</a>
					<div
						v-if="hasCaption(message.message)"
						v-html="formatWhatsAppMessage(message.message)"
					/>
				</div>
				<div v-else-if="contentType == 'audio'">
					<!-- the native player has a ~300px min width, so it must be allowed to shrink -->
					<audio :src="message.media_url" controls class="w-full" />
				</div>
				<div v-else-if="contentType == 'video'">
					<video
						:src="message.media_url"
						controls
						class="max-h-72 w-full rounded bg-black object-contain"
					/>
					<div
						v-if="hasCaption(message.message)"
						class="mt-1.5"
						v-html="formatWhatsAppMessage(message.message)"
					/>
				</div>

				<!--
					A border rather than a ring: frappe-ui registers `ringColor` for `outline`
					only, so `ring-surface-*` silently falls back to Tailwind's default blue ring.
					The chip straddles the bubble and the page, so it carries its own surface.
				-->
				<div
					v-if="message.reactions?.length"
					data-slot="reactions"
					class="absolute -bottom-0.5 right-2 flex translate-y-1/2 gap-0.5 rounded-full border border-outline-gray-2 bg-surface-base px-1.5 py-0.5 text-sm shadow-sm"
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
			</div>

			<!--
				Beside the coloured body and centred on it, so the pair tracks the bubble rather
				than the taller body-plus-footer column. Revealed by focus as well as hover, and
				inert to the pointer until then: an invisible button must not be clickable, but
				must still be reachable by keyboard.
			-->
			<div
				v-if="message.status != 'Failed'"
				class="pointer-events-none flex shrink-0 items-center gap-0.5 opacity-0 group-hover/bubble:pointer-events-auto group-hover/bubble:opacity-100 group-focus-within/bubble:pointer-events-auto group-focus-within/bubble:opacity-100"
			>
				<Button
					variant="ghost"
					size="xs"
					:tooltip="replyLabel"
					:aria-label="replyLabel"
					@click="emit('reply', message)"
				>
					<template #icon>
						<span class="lucide-corner-up-left size-4" aria-hidden="true" />
					</template>
				</Button>

				<slot name="actions" />
			</div>
		</div>

		<!--
			Outside the coloured body, so the blue Read tick sits on the page background rather
			than on the bubble. Room for an overhanging reaction chip comes from the body's own
			`has-[]` margin, not from a margin computed per row.
		-->
		<div
			class="flex max-w-full items-center gap-1.5 px-1 text-xs text-ink-gray-6 group-data-[direction=Outgoing]/bubble:flex-row-reverse"
		>
			<Tooltip :text="creation.format('ddd, MMM D, YYYY')">
				<!--
					dayjsLocal, not dayjs: `creation` is naive and in the site's timezone,
					so plain dayjs would read it as browser-local and shift every stamp.
				-->
				<time :datetime="creation.format('YYYY-MM-DDTHH:mm:ssZ')">
					{{ creation.format("hh:mm a") }}
				</time>
			</Tooltip>

			<template v-if="message.direction == 'Outgoing'">
				<LoadingIndicator v-if="message.status == 'Pending'" class="size-3" />
				<span
					v-else-if="message.status == 'Sent'"
					class="lucide-check size-4"
					aria-hidden="true"
				/>
				<span
					v-else-if="['Read', 'Delivered'].includes(message.status || '')"
					class="lucide-check-check size-4"
					:class="{ 'text-ink-blue-6': message.status == 'Read' }"
					aria-hidden="true"
				/>
			</template>

			<!-- readable rather than hover-only: a send failure is the one thing worth reading -->
			<span v-if="message.status == 'Failed'" class="min-w-0 break-words text-ink-red-7">
				{{ message.error_message || failedMessageLabel }}
			</span>
		</div>
	</div>
</template>
