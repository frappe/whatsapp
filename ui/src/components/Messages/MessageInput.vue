<!-- eslint-disable vue/no-v-html -->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { Button, Dropdown, FileUploader, Textarea, Tooltip } from "frappe-ui";
import MediaPreviewDialog from "../common/MediaPreviewDialog.vue";
import { formatWhatsAppMessage } from "../../utils/formatMessage";
import { contentTypeFromMime } from "../../utils/media";
import type {
	MediaFile,
	MessageInputProps,
	MessagesController,
	SendMessagePayload,
	WhatsAppContentType,
} from "./types";

/** The controller half arrives whole from `v-bind="messages"`; the rest is chrome. */
const props = withDefaults(defineProps<MessagesController & MessageInputProps>(), {
	placeholder: "Type your message here...",
	senderName: "Contact",
	youLabel: "You",
	uploadDocumentLabel: "Upload Document",
	uploadImageLabel: "Upload Image",
	uploadVideoLabel: "Upload Video",
	captionPlaceholder: "Add a caption...",
	sendLabel: "Send",
	replyingToLabel: "Replying to",
	dismissReplyLabel: "Dismiss reply",
	windowClosedLabel:
		"The 24-hour customer service window has closed. Send a template to reopen it.",
	windowUnopenedLabel: "Send a template to start the conversation.",
});

const emit = defineEmits<{
	send: [payload: SendMessagePayload];
}>();

// View state only; nothing here is part of the message being composed.
const textareaRef = ref<{ el?: HTMLTextAreaElement } | null>(null);
const uploaderRef = ref<{ inputRef?: HTMLInputElement } | null>(null);
const acceptedFileTypes = ref<string>();
const showMediaPreview = ref(false);
const draggingOver = ref(false);
// Which menu item was clicked, remembered until the upload succeeds.
const pickedType = ref<WhatsAppContentType>("document");

const draft = computed({
	get: () => props.draft,
	set: (value: string) => props.setDraft(value),
});

const replyToName = computed(() =>
	props.replyTo?.direction === "Incoming" ? props.senderName : props.youLabel
);

// The window is a guess from the loaded messages, so it only informs; Meta's own refusal
// is what stops a send that is really outside it.
const windowStatus = computed(() => props.serviceWindow?.status ?? "open");
const windowNotice = computed(() => {
	switch (windowStatus.value) {
		case "closed":
			return props.windowClosedLabel;
		case "unopened":
			return props.windowUnopenedLabel;
		default:
			return null;
	}
});
const locked = computed(() => props.disabled);
const sendable = computed(() => props.canSend && !locked.value);

function focus() {
	nextTick(() => textareaRef.value?.el?.focus());
}

/**
 * The payload is built only to be reported: reading it before the send lets the emit
 * describe what went out, after the controller has cleared it.
 */
async function submit(overrides?: Pick<SendMessagePayload, "message">) {
	if (!sendable.value) return;
	const payload = props.buildPayload(overrides);
	const name = await props.send(overrides);
	if (name && payload) emit("send", payload);
}

// Shift+enter is left to the textarea, so it breaks the line. An enter that commits an IME
// composition is neither a send nor a line break.
function sendOnEnter(event: KeyboardEvent) {
	if (event.isComposing) return;
	event.preventDefault();
	submit();
}

// Preview first rather than sending immediately, so the user can add a caption.
function onUpload(file: MediaFile) {
	props.attach(file, pickedType.value);
	showMediaPreview.value = true;
}

// The caption overrides the body instead of being written into the draft, so anything
// already typed stays in the box as the separate unsent message it is.
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

/**
 * FileUploader has no method for uploading a `File` we already hold, so a dropped or
 * pasted one is handed to the input it exposes — the same path a file-picker choice takes.
 */
function upload(file: File) {
	const input = uploaderRef.value?.inputRef;
	if (!input) return;
	const kind = contentTypeFromMime(file.type);
	pickedType.value = kind === "text" ? "document" : kind;
	acceptedFileTypes.value = undefined;

	const transfer = new DataTransfer();
	transfer.items.add(file);
	input.files = transfer.files;
	input.dispatchEvent(new Event("change"));
}

function onDrop(event: DragEvent) {
	draggingOver.value = false;
	const file = event.dataTransfer?.files?.[0];
	if (file && !locked.value) upload(file);
}

// Only when the clipboard actually carries a file — pasting text must stay a paste.
function onPaste(event: ClipboardEvent) {
	const file = event.clipboardData?.files?.[0];
	if (!file || locked.value) return;
	event.preventDefault();
	upload(file);
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
	<!-- The dialog is a sibling of the composer, so a host's `class` needs a root above both. -->
	<div class="flex flex-col gap-2">
		<div
			v-if="windowNotice"
			role="status"
			class="flex items-center gap-2 rounded-lg bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-7"
		>
			<span class="lucide-info size-4 shrink-0 text-ink-amber-6" aria-hidden="true" />
			{{ windowNotice }}
		</div>

		<!--
			One control rather than a field beside a button row: the reply preview, the field and
			the actions all sit inside the box, so they share its focus ring, its disabled state
			and its drop target. `overflow-hidden` keeps the preview's fill inside the rounded
			corners — the attach menu and the send tooltip both portal out, so neither is clipped.
		-->
		<div
			class="overflow-hidden rounded-lg border bg-surface-base transition-colors focus-within:border-outline-gray-3"
			:class="
				draggingOver ? 'border-outline-blue-3 bg-surface-blue-1' : 'border-outline-gray-2'
			"
			@dragover.prevent="draggingOver = true"
			@dragleave="draggingOver = false"
			@drop.prevent="onDrop"
			@paste="onPaste"
		>
			<!-- a rule and two lines rather than a nested card: the preview belongs to the box -->
			<div
				v-if="replyTo"
				class="flex items-center gap-2 border-b border-outline-gray-2 bg-surface-gray-1 py-2 pl-2.5 pr-1.5"
			>
				<div class="min-w-0 flex-1 border-l-2 border-outline-gray-3 pl-2">
					<div class="text-sm text-ink-gray-6">
						{{ replyingToLabel }} {{ replyToName }}
					</div>
					<!-- clamped, not cropped: a fixed max-height slices the last line in half -->
					<div
						class="line-clamp-2 text-p-base text-ink-gray-7"
						v-html="formatWhatsAppMessage(replyTo.message)"
					/>
				</div>

				<Button variant="ghost" :aria-label="dismissReplyLabel" @click="clearReply()">
					<template #icon>
						<span class="lucide-circle-x size-4 text-ink-gray-6" aria-hidden="true" />
					</template>
				</Button>
			</div>

			<!-- placeholder overridden: ghost's own is ink-gray-3, 1.5:1 on white -->
			<Textarea
				ref="textareaRef"
				v-model="draft"
				variant="ghost"
				class="max-h-40 min-h-9 w-full resize-none border-0 bg-transparent placeholder-ink-gray-5 [field-sizing:content]"
				:rows="1"
				:placeholder="placeholder"
				:disabled="locked"
				@keydown.enter.exact="sendOnEnter"
			/>

			<div class="flex items-center gap-1 px-1.5 pb-1.5">
				<slot name="leading-actions" />

				<FileUploader
					ref="uploaderRef"
					:file-types="acceptedFileTypes"
					@success="onUpload"
				>
					<template #default="{ openFileSelector }">
						<Dropdown :options="uploadOptions(openFileSelector)">
							<Button variant="ghost" :disabled="locked" aria-label="Attach a file">
								<template #icon>
									<span class="lucide-plus size-4.5" aria-hidden="true" />
								</template>
							</Button>
						</Dropdown>
					</template>
				</FileUploader>

				<div class="flex-1" />

				<Tooltip>
					<template #content>
						<span class="flex items-center gap-1">
							{{ sendLabel }}
							<kbd class="rounded-sm bg-surface-gray-7 px-1 text-xs text-ink-gray-2"
								>↵</kbd
							>
						</span>
					</template>
					<Button
						variant="solid"
						:disabled="!sendable"
						:loading="sending"
						:aria-label="sendLabel"
						@click="submit()"
					>
						<template #icon>
							<span class="lucide-arrow-up size-4" aria-hidden="true" />
						</template>
					</Button>
				</Tooltip>
			</div>
		</div>

		<MediaPreviewDialog
			v-model:open="showMediaPreview"
			:file="pendingMedia"
			:type="pendingType"
			:loading="sending"
			:caption-placeholder="captionPlaceholder"
			@send="onMediaSend"
		/>
	</div>
</template>
