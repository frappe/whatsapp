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

const sendable = computed(() => props.canSend && !props.disabled);

// Only the platform knows which modifier to name, so it is detected rather than passed in.
const modifierKey = computed(() =>
	typeof navigator !== "undefined" &&
	/Mac|iP(hone|ad|od)/.test(navigator.platform || navigator.userAgent)
		? "⌘"
		: "Ctrl"
);

function focus() {
	nextTick(() => textareaRef.value?.el?.focus());
}

/**
 * The payload is built only to be reported: reading it before the send lets the emit
 * describe what went out, after the controller has cleared it.
 */
async function submit(overrides?: Pick<SendMessagePayload, "message">) {
	if (props.disabled) return;
	const payload = props.buildPayload(overrides);
	const name = await props.send(overrides);
	if (name && payload) emit("send", payload);
}

function sendText() {
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
	if (file && !props.disabled) upload(file);
}

// Only when the clipboard actually carries a file — pasting text must stay a paste.
function onPaste(event: ClipboardEvent) {
	const file = event.clipboardData?.files?.[0];
	if (!file || props.disabled) return;
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
	<!--
		Single root, so a host's `class` insets the reply preview and the composer together.
		They were two roots, and a gutter passed in landed on the composer alone.
	-->
	<div class="flex flex-col">
		<div v-if="replyTo" class="flex items-center gap-2 pb-2">
			<div
				class="min-w-0 flex-1 rounded border-l-2 border-outline-gray-3 bg-surface-gray-3 p-2"
			>
				<div class="mb-0.5 text-sm text-ink-gray-6">
					{{ replyingToLabel }} {{ replyToName }}
				</div>
				<!-- clamped, not cropped: a fixed max-height slices the last line in half -->
				<div
					class="line-clamp-2 text-p-base text-ink-gray-7"
					v-html="formatWhatsAppMessage(replyTo.message)"
				/>
			</div>

			<Button variant="ghost" aria-label="Dismiss reply" @click="clearReply()">
				<template #icon>
					<span class="lucide-circle-x size-4 text-ink-gray-6" aria-hidden="true" />
				</template>
			</Button>
		</div>

		<!--
			One control rather than a field beside a button row: the actions sit inside the box
			so they share its focus ring, its disabled state and its drop target.
		-->
		<div
			class="rounded-lg border bg-surface-base transition-colors focus-within:border-outline-gray-3"
			:class="
				draggingOver ? 'border-outline-blue-3 bg-surface-blue-1' : 'border-outline-gray-2'
			"
			@dragover.prevent="draggingOver = true"
			@dragleave="draggingOver = false"
			@drop.prevent="onDrop"
			@paste="onPaste"
		>
			<!-- placeholder overridden: ghost's own is ink-gray-3, 1.5:1 on white -->
			<Textarea
				ref="textareaRef"
				v-model="draft"
				variant="ghost"
				class="max-h-40 min-h-9 w-full resize-none border-0 bg-transparent placeholder-ink-gray-5 [field-sizing:content]"
				:rows="1"
				:placeholder="placeholder"
				:disabled="disabled"
				@keydown.ctrl.enter.stop="sendText"
				@keydown.meta.enter.stop="sendText"
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
							<Button
								variant="ghost"
								:disabled="disabled"
								aria-label="Attach a file"
							>
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
							<kbd
								class="rounded-sm bg-surface-gray-7 px-1 text-xs text-ink-gray-2"
								>{{ modifierKey }}</kbd
							>
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
