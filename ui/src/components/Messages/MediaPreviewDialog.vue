<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { Button, Dialog, Textarea, formatBytes } from "frappe-ui";
import DocumentIcon from "./icons/DocumentIcon.vue";
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

const fileSize = computed(() => (props.file?.file_size ? formatBytes(props.file.file_size) : ""));

function submit() {
	emit("send", caption.value);
	show.value = false;
}

function onEnter(event: KeyboardEvent) {
	if (event.shiftKey) return;
	submit();
}

// Reset the caption each time the dialog opens, and focus the input.
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
			<!-- media preview -->
			<div class="flex justify-center rounded-md bg-surface-gray-2 p-2">
				<img
					v-if="type === 'image'"
					:src="file?.file_url"
					class="max-h-80 rounded-md object-contain"
				/>
				<video
					v-else-if="type === 'video'"
					:src="file?.file_url"
					controls
					class="max-h-80 rounded-md"
				/>
				<div v-else class="flex w-full items-center gap-2 p-2">
					<DocumentIcon class="size-10 flex-shrink-0 text-ink-gray-4" />
					<div class="flex min-w-0 flex-col">
						<div class="truncate text-ink-gray-8">{{ file?.file_name }}</div>
						<div v-if="fileSize" class="text-sm text-ink-gray-5">
							{{ fileSize }}
						</div>
					</div>
				</div>
			</div>

			<!-- caption (negative bottom margin trims the Dialog body's default pb-6) -->
			<div class="-mb-4 mt-3 flex items-end gap-2">
				<Textarea
					ref="captionRef"
					v-model="caption"
					class="w-full"
					:rows="1"
					:placeholder="captionPlaceholder"
					@keydown.enter.stop="onEnter"
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
