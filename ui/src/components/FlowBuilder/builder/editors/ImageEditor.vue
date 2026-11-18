<script setup lang="ts">
import { computed, ref } from "vue";
import { Button } from "frappe-ui";
import { IMAGE_FILE, type Block, type Screen } from "../../model";
import { useBlock } from "./useBlock";

/** Meta's drop zone. The Flow JSON carries the image itself, base64 encoded, in `src`. */
const props = defineProps<{ block: Block; screen: Screen }>();
const { session, chrome, value, set, error } = useBlock(props);

const picker = ref<HTMLInputElement>();
const over = ref(false);
const refused = ref("");

const source = computed(() => value("src"));
const preview = computed(() => {
	if (!source.value) return "";
	const type = source.value.startsWith("/9j/") ? "jpeg" : "png";
	return `data:image/${type};base64,${source.value}`;
});
const message = computed(() => refused.value || error("src"));

async function take(file: File | undefined) {
	over.value = false;
	if (!file) return;
	if (!IMAGE_FILE.types.includes(file.type))
		return (refused.value = chrome.value.imageWrongType);
	if (file.size > IMAGE_FILE.maxBytes) return (refused.value = chrome.value.imageTooLarge);
	refused.value = "";
	set("src", await base64(file));
}

function base64(file: File): Promise<string> {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
		reader.onerror = () => reject(reader.error);
		reader.readAsDataURL(file);
	});
}
</script>

<template>
	<div class="flex flex-col gap-1.5">
		<div
			class="flex items-center gap-3 rounded-5 border border-dashed p-3 transition-colors duration-150"
			:class="[
				over ? 'border-outline-gray-4 bg-surface-gray-2' : 'border-outline-gray-2',
				message ? 'border-outline-red-3' : '',
			]"
			@dragover.prevent="over = !session.readOnly"
			@dragleave="over = false"
			@drop.prevent="!session.readOnly && take($event.dataTransfer?.files[0])"
		>
			<img
				v-if="preview"
				:src="preview"
				alt=""
				class="size-12 shrink-0 rounded-4 object-cover"
			/>
			<span
				v-else
				class="flex size-12 shrink-0 items-center justify-center rounded-4 bg-surface-gray-2"
			>
				<span class="lucide-image size-5 text-ink-gray-5" aria-hidden="true" />
			</span>
			<div class="flex min-w-0 flex-1 flex-col gap-1">
				<p class="text-p-sm text-ink-gray-6">{{ chrome.dropImage }}</p>
			</div>
			<Button
				v-if="!session.readOnly"
				:label="source ? chrome.replaceImage : chrome.chooseImage"
				@click="picker?.click()"
			/>
			<input
				ref="picker"
				type="file"
				class="hidden"
				:accept="IMAGE_FILE.types.join(',')"
				@change="take(($event.target as HTMLInputElement).files?.[0])"
			/>
		</div>
		<p v-if="message" class="text-p-sm text-ink-red-5" role="alert">{{ message }}</p>
	</div>
</template>
