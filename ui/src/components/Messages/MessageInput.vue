<!-- eslint-disable vue/no-v-html -->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { Button, Dropdown, FileUploader, Textarea } from "frappe-ui";
import MediaPreviewDialog from "./MediaPreviewDialog.vue";
import { formatWhatsAppMessage } from "./formatMessage";
import type {
	MediaFile,
	MessageInputProps,
	MessagesController,
	SendMessagePayload,
	WhatsAppContentType,
} from "./types";

// Multi-root template: Vue cannot auto-inherit attrs onto a fragment, so they are
// bound explicitly onto the input row below. Without this, any attribute a host
// passes down warns at dev time.
defineOptions({ inheritAttrs: false });

/**
 * The controller half of these props arrives whole from `v-bind="messages"`; the rest is
 * chrome. Every piece of composing state is read off the controller, written back through
 * its verbs, and sent by its `send()`, so this component is interchangeable with a host's
 * own input.
 */
const props = withDefaults(defineProps<MessagesController & MessageInputProps>(), {
	placeholder: "Type your message here...",
	senderName: "Contact",
	youLabel: "You",
	uploadDocumentLabel: "Upload Document",
	uploadImageLabel: "Upload Image",
	uploadVideoLabel: "Upload Video",
	captionPlaceholder: "Add a caption...",
});

const emit = defineEmits<{
	send: [payload: SendMessagePayload];
}>();

// View state only — how tall the box is, which accept filter the hidden input carries, and
// whether the preview dialog is up. None of it is part of the message being composed.
const rows = ref(1);
const textareaRef = ref<{ el?: HTMLTextAreaElement } | null>(null);
const acceptedFileTypes = ref<string>();
const showMediaPreview = ref(false);
// Which menu item was clicked, remembered until the upload succeeds and there is a file to
// hand to `attach()`.
const pickedType = ref<WhatsAppContentType>("document");

const draft = computed({
	get: () => props.draft,
	set: (value: string) => props.setDraft(value),
});

/** The reply preview names the quoted message's side, the same way a bubble does. */
const replyToName = computed(() =>
	props.replyTo?.direction === "Incoming" ? props.senderName : props.youLabel
);

function focus() {
	nextTick(() => textareaRef.value?.el?.focus());
}

/**
 * Send through the controller, which owns the call, the empty-send guard (a `null` payload
 * means no body and no attachment) and the clearing that follows.
 *
 * The payload is assembled here only to be reported: `buildPayload` is pure, and reading it
 * before the send lets the emit describe what went out after the controller has cleared it.
 */
async function submit(overrides?: Pick<SendMessagePayload, "message">) {
	if (props.disabled) return;
	const payload = props.buildPayload(overrides);
	const name = await props.send(overrides);
	if (name && payload) emit("send", payload);
}

function sendText(event: KeyboardEvent) {
	if (event.shiftKey) return;
	submit();
	textareaRef.value?.el?.blur();
}

// Open the caption/preview dialog instead of sending the media immediately,
// so the user can attach a caption (Telegram-style).
function onUpload(file: MediaFile) {
	props.attach(file, pickedType.value);
	showMediaPreview.value = true;
}

// The caption is the media message's body, and it is typed in the dialog, not in the input.
// It overrides the body rather than being written into the draft, so anything already typed
// stays in the box as the unsent message it is — the controller clears only the attachment
// and the reply after a media send.
function onMediaSend(caption: string) {
	submit({ message: caption });
}

/**
 * The accept filter is FileUploader's `fileTypes` prop, not an argument to
 * `openFileSelector()`, so it has to reach the hidden input before it is clicked.
 */
function pickFile(
	type: WhatsAppContentType,
	accept: string | undefined,
	openFileSelector: () => void
) {
	pickedType.value = type;
	acceptedFileTypes.value = accept;
	nextTick(openFileSelector);
}

function uploadOptions(openFileSelector: () => void) {
	return [
		{
			label: props.uploadDocumentLabel,
			icon: "lucide-file",
			onClick: () => pickFile("document", undefined, openFileSelector),
		},
		{
			label: props.uploadImageLabel,
			icon: "lucide-image",
			onClick: () => pickFile("image", "image/*", openFileSelector),
		},
		{
			label: props.uploadVideoLabel,
			icon: "lucide-video",
			onClick: () => pickFile("video", "video/*", openFileSelector),
		},
	];
}

watch(
	() => props.replyTo,
	(value) => value && focus()
);

// Dismissing the preview abandons the upload; leaving it staged would attach it to whatever
// is typed next. A send has already cleared it by the time this runs.
watch(showMediaPreview, (open) => {
	if (!open && props.pendingMedia) props.clearAttachment();
});

defineExpose({ focus });
</script>

<template>
	<div v-if="replyTo" class="flex items-center justify-around gap-2 px-3 pt-2 sm:px-10">
		<div
			class="mb-1 flex-1 rounded border-0 border-l-4 bg-surface-gray-2 p-2 text-base text-ink-gray-5"
			:class="replyTo.direction == 'Incoming' ? 'border-green-500' : 'border-blue-400'"
		>
			<div
				class="mb-1 text-sm-bold"
				:class="
					replyTo.direction == 'Incoming' ? 'text-ink-green-5' : 'text-ink-blue-link'
				"
			>
				{{ replyToName }}
			</div>
			<div
				class="max-h-12 overflow-hidden"
				v-html="formatWhatsAppMessage(replyTo.message)"
			/>
		</div>

		<Button variant="ghost" icon="lucide-x" aria-label="Dismiss reply" @click="clearReply()" />
	</div>

	<div class="flex items-end gap-2 px-3 py-2.5 sm:px-10" v-bind="$attrs">
		<div class="flex h-8 items-center gap-2">
			<FileUploader :file-types="acceptedFileTypes" @success="onUpload">
				<template #default="{ openFileSelector }">
					<div class="flex items-center space-x-2">
						<Dropdown :options="uploadOptions(openFileSelector)">
							<!-- P12: the bare icon needs an accessible name -->
							<span
								class="lucide-plus size-4.5 cursor-pointer text-ink-gray-5"
								:class="disabled ? 'pointer-events-none opacity-50' : ''"
								aria-label="Attach a file"
							/>
						</Dropdown>
					</div>
				</template>
			</FileUploader>
		</div>

		<Textarea
			ref="textareaRef"
			v-model="draft"
			class="min-h-8 w-full"
			:rows="rows"
			:placeholder="placeholder"
			:disabled="disabled"
			@focus="rows = 6"
			@blur="rows = 1"
			@keydown.enter.stop="sendText"
		/>
	</div>

	<MediaPreviewDialog
		v-model:open="showMediaPreview"
		:file="pendingMedia"
		:type="pendingType"
		:caption-placeholder="captionPlaceholder"
		@send="onMediaSend"
	/>
</template>
