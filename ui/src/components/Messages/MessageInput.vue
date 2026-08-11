<!-- eslint-disable vue/no-v-html -->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { Button, Dropdown, FileUploader, Textarea } from "frappe-ui";
import MediaPreviewDialog from "../common/MediaPreviewDialog.vue";
import { formatWhatsAppMessage } from "../../utils/formatMessage";
import type {
	MediaFile,
	MessageInputProps,
	MessagesController,
	SendMessagePayload,
	WhatsAppContentType,
} from "./types";

// Multi-root template: Vue cannot auto-inherit attrs onto a fragment, so $attrs is bound
// explicitly onto the input row below.
defineOptions({ inheritAttrs: false });

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
const MAX_ROWS = 6;
const textareaRef = ref<{ el?: HTMLTextAreaElement } | null>(null);
const acceptedFileTypes = ref<string>();
const showMediaPreview = ref(false);
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

function focus() {
	nextTick(() => textareaRef.value?.el?.focus());
}

/**
 * Grow with the content rather than with focus. `height: auto` first so scrollHeight reports
 * the text's own height instead of the height already set on the element.
 */
function autosize() {
	const el = textareaRef.value?.el;
	if (!el) return;
	el.style.height = "auto";
	const lineHeight = parseFloat(getComputedStyle(el).lineHeight) || 20;
	const max = lineHeight * MAX_ROWS;
	el.style.height = `${Math.min(el.scrollHeight, max)}px`;
	el.style.overflowY = el.scrollHeight > max ? "auto" : "hidden";
}

watch(() => props.draft, () => nextTick(autosize));
onMounted(autosize);

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
	<div v-if="replyTo" class="flex items-center gap-2 px-3 pt-2 sm:px-10">
		<div class="min-w-0 flex-1 rounded border-l-2 border-outline-gray-3 bg-surface-gray-1 p-2">
			<div class="mb-0.5 text-sm text-ink-gray-5">
				{{ replyingToLabel }} {{ replyToName }}
			</div>
			<div
				class="max-h-12 overflow-hidden text-base text-ink-gray-7"
				v-html="formatWhatsAppMessage(replyTo.message)"
			/>
		</div>

		<Button variant="ghost" aria-label="Dismiss reply" @click="clearReply()">
			<template #icon>
				<span class="lucide-circle-x size-4 text-ink-gray-5" aria-hidden="true" />
			</template>
		</Button>
	</div>

	<div class="flex items-end gap-2 px-3 py-2.5 sm:px-10" v-bind="$attrs">
		<Textarea
			ref="textareaRef"
			v-model="draft"
			class="min-h-8 w-full resize-none"
			:rows="1"
			:placeholder="placeholder"
			:disabled="disabled"
			@keydown.ctrl.enter.stop="sendText"
			@keydown.meta.enter.stop="sendText"
		/>

		<div class="flex h-8 items-center gap-1">
			<slot name="leading-actions" />

			<FileUploader :file-types="acceptedFileTypes" @success="onUpload">
				<template #default="{ openFileSelector }">
					<Dropdown :options="uploadOptions(openFileSelector)">
						<Button variant="ghost" :disabled="disabled" aria-label="Attach a file">
							<template #icon>
								<span class="lucide-plus size-4.5" aria-hidden="true" />
							</template>
						</Button>
					</Dropdown>
				</template>
			</FileUploader>

			<Button
				variant="solid"
				:disabled="!sendable"
				:label="sendLabel"
				@click="submit()"
			/>
		</div>
	</div>

	<MediaPreviewDialog
		v-model:open="showMediaPreview"
		:file="pendingMedia"
		:type="pendingType"
		:caption-placeholder="captionPlaceholder"
		@send="onMediaSend"
	/>
</template>
