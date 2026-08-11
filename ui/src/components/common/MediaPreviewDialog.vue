<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { Button, Dialog, Textarea } from "frappe-ui";
import { documentMeta, documentName } from "../../utils/media";
import type { MediaPreviewDialogProps } from "./types";

const props = withDefaults(defineProps<MediaPreviewDialogProps>(), {
	type: "image",
	captionPlaceholder: "Add a caption...",
	cancelLabel: "Cancel",
	sendLabel: "Send",
});

const emit = defineEmits<{
	send: [caption: string];
	"update:open": [value: boolean];
}>();

const caption = ref("");
const captionRef = ref<{ el?: HTMLTextAreaElement } | null>(null);

const show = computed({
	get: () => props.open,
	set: (value: boolean) => emit("update:open", value),
});

const dialogTitle = computed(() => {
	if (props.title) return props.title;
	if (props.type === "image") return "Send an image";
	if (props.type === "video") return "Send a video";
	return "Send a file";
});

// The same derivations the bubble uses, so a file is named and sized identically either side
// of the send. `MediaFile` calls the URL `file_url`; `MediaAttachment` calls it `media_url`.
const attachment = computed(() => ({
	media_url: props.file?.file_url,
	file_name: props.file?.file_name,
	file_size: props.file?.file_size,
}));

function submit() {
	emit("send", caption.value);
	show.value = false;
}

watch(
	() => props.open,
	(value) => {
		if (value) {
			caption.value = "";
			nextTick(() => captionRef.value?.el?.focus());
		}
	}
);
</script>

<template>
	<Dialog v-model="show" :options="{ title: dialogTitle, size: 'lg' }">
		<template #body-content>
			<div class="flex justify-center rounded-md bg-surface-gray-2 p-2">
				<img
					v-if="type === 'image'"
					:src="file?.file_url"
					:alt="documentName(attachment, 'Image')"
					class="max-h-80 rounded-md object-contain"
				/>
				<video
					v-else-if="type === 'video'"
					:src="file?.file_url"
					controls
					class="max-h-80 rounded-md"
				/>
				<div v-else class="flex w-full items-center gap-2 p-2">
					<span
						class="lucide-file-text size-10 flex-shrink-0 text-ink-gray-4"
						aria-hidden="true"
					/>
					<div class="flex min-w-0 flex-col">
						<div class="truncate text-ink-gray-8">{{ documentName(attachment) }}</div>
						<div v-if="documentMeta(attachment)" class="text-sm text-ink-gray-6">
							{{ documentMeta(attachment) }}
						</div>
					</div>
				</div>
			</div>

			<div class="mt-3">
				<Textarea
					ref="captionRef"
					v-model="caption"
					class="w-full"
					:rows="1"
					:placeholder="captionPlaceholder"
					@keydown.ctrl.enter.stop="submit"
					@keydown.meta.enter.stop="submit"
				/>
			</div>
		</template>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button :label="cancelLabel" @click="show = false" />
				<Button :label="sendLabel" variant="solid" :loading="loading" @click="submit" />
			</div>
		</template>
	</Dialog>
</template>
