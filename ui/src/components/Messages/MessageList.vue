<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { Button, LoadingIndicator, dayjsLocal } from "frappe-ui";
import MessageBubble from "./MessageBubble.vue";
import ReactionPicker, { REACTION_EMOJIS } from "../common/ReactionPicker.vue";
import type { MessageListProps, ReactPayload, WhatsAppMessage } from "./types";

const props = withDefaults(defineProps<MessageListProps>(), {
	messages: () => [],
	rowClass: "",
	senderName: "Contact",
	youLabel: "You",
	reactedByLabel: "Reacted by",
	replyLabel: "Reply",
	replyingToLabel: "Replying to",
	failedMessageLabel: "Failed to send message",
	reactLabel: "React",
	emptyLabel: "No messages yet",
	emptyDescription: "Messages sent to and from this contact will appear here.",
	errorLabel: "Could not load messages",
	todayLabel: "Today",
	yesterdayLabel: "Yesterday",
	reactionEmojis: () => REACTION_EMOJIS,
});

const emit = defineEmits<{
	reply: [message: WhatsAppMessage];
	react: [payload: ReactPayload];
}>();

const FLASH_MS = 1000;

type Row =
	| { kind: "separator"; key: string; label: string }
	| { kind: "message"; key: string; message: WhatsAppMessage };

function dayLabel(creation: string) {
	const day = dayjsLocal(creation);
	const today = dayjsLocal();
	if (day.isSame(today, "day")) return props.todayLabel;
	if (day.isSame(today.subtract(1, "day"), "day")) return props.yesterdayLabel;
	return day.format("MMMM D, YYYY");
}

/** The conversation stays flat; the only structure imposed is a rule between calendar days. */
const rows = computed<Row[]>(() => {
	const out: Row[] = [];
	let previousDay = "";
	for (const message of props.messages) {
		const day = dayjsLocal(message.creation).format("YYYY-MM-DD");
		if (day !== previousDay) {
			previousDay = day;
			out.push({ kind: "separator", key: `day-${day}`, label: dayLabel(message.creation) });
		}
		out.push({ kind: "message", key: message.name, message });
	}
	return out;
});

// Scoped to this list: two lists on one page would otherwise fight over `document`, and a
// docname shares the id namespace with every other element on the page.
const rowElements = new Map<string, HTMLElement>();
const flashed = ref<string | null>(null);
let flashTimer: ReturnType<typeof setTimeout> | undefined;

function registerRow(name: string, element: unknown) {
	if (element) rowElements.set(name, element as HTMLElement);
	else rowElements.delete(name);
}

/** Jump to a quoted message and flash it, so the reader can find it in a long thread. */
function scrollToMessage(name: string) {
	const element = rowElements.get(name);
	if (!element) return;
	// `center`, not the default `start`: this package draws no scroll container, so it
	// cannot know what sticky chrome the host has parked at the top.
	element.scrollIntoView({ behavior: "smooth", block: "center" });

	clearTimeout(flashTimer);
	flashed.value = name;
	flashTimer = setTimeout(() => (flashed.value = null), FLASH_MS);
}

onBeforeUnmount(() => clearTimeout(flashTimer));
</script>

<template>
	<div role="log" aria-relevant="additions">
		<!-- spinner only on first load; cached messages stay visible while revalidating -->
		<div v-if="loading && !messages.length" class="flex justify-center py-8">
			<LoadingIndicator class="size-5 text-ink-gray-5" />
		</div>

		<!-- distinct from empty: a failed fetch must not read as "nothing was ever sent" -->
		<div
			v-else-if="error && !messages.length"
			class="flex flex-col items-center gap-2 rounded-lg border border-dashed border-outline-gray-2 p-6 text-center"
		>
			<span
				class="grid size-7 place-items-center rounded-md bg-surface-gray-3 text-ink-gray-7"
				aria-hidden="true"
			>
				<span class="lucide-triangle-alert size-4" />
			</span>
			<div class="text-base font-medium text-ink-gray-8">{{ errorLabel }}</div>
		</div>

		<div
			v-else-if="!messages.length"
			class="flex flex-col items-center gap-2 rounded-lg border border-dashed border-outline-gray-2 p-6 text-center"
		>
			<span
				class="grid size-7 place-items-center rounded-md bg-surface-gray-3 text-ink-gray-7"
				aria-hidden="true"
			>
				<span class="lucide-message-circle size-4" />
			</span>
			<div class="text-base font-medium text-ink-gray-8">{{ emptyLabel }}</div>
			<div v-if="emptyDescription" class="text-sm text-ink-gray-6">
				{{ emptyDescription }}
			</div>
		</div>

		<ul v-else role="list" class="flex flex-col gap-3">
			<template v-for="row in rows" :key="row.key">
				<li
					v-if="row.kind === 'separator'"
					role="presentation"
					class="flex items-center gap-3 py-1"
				>
					<!-- a border, not a background: `bg-` registers `surface` only, so
					     `bg-outline-*` produces no colour at all -->
					<span class="flex-1 border-t border-outline-gray-2" />
					<span class="text-xs text-ink-gray-6">{{ row.label }}</span>
					<span class="flex-1 border-t border-outline-gray-2" />
				</li>

				<li
					v-else
					:ref="(el) => registerRow(row.message.name, el)"
					class="group flex gap-2 rounded-lg transition-shadow [contain-intrinsic-size:auto_5rem] [content-visibility:auto]"
					:class="[
						rowClass,
						row.message.direction == 'Outgoing' ? 'flex-row-reverse' : '',
						flashed === row.message.name ? 'ring-2 ring-outline-blue-3' : '',
					]"
				>
					<!--
						`empty:hidden` so a slot that renders nothing for this message — an
						outgoing one, say — costs no width and no gap. Aligned to the top of the
						bubble rather than the bottom of the row, which is under the footer.
					-->
					<div v-if="$slots.avatar" class="shrink-0 self-start empty:hidden">
						<slot name="avatar" :message="row.message" />
					</div>

					<MessageBubble
						:message="row.message"
						:sender-name="senderName"
						:you-label="youLabel"
						:reacted-by-label="reactedByLabel"
						:reply-label="replyLabel"
						:replying-to-label="replyingToLabel"
						:failed-message-label="failedMessageLabel"
						@reply="emit('reply', $event)"
						@jump-to="scrollToMessage"
					>
						<!-- the bubble owns the reveal and the Failed guard for this whole pair -->
						<template #actions>
							<ReactionPicker
								v-slot="{ togglePopover }"
								:emojis="reactionEmojis"
								@select="
									emit('react', { messageName: row.message.name, emoji: $event })
								"
							>
								<Button
									variant="ghost"
									size="xs"
									:aria-label="reactLabel"
									@click="togglePopover"
								>
									<template #icon>
										<span
											class="lucide-smile-plus size-4 text-ink-gray-7"
											aria-hidden="true"
										/>
									</template>
								</Button>
							</ReactionPicker>
						</template>
					</MessageBubble>
				</li>
			</template>
		</ul>
	</div>
</template>
