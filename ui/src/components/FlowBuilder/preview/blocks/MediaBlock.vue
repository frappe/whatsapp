<script setup lang="ts">
import { computed } from "vue";
import type { Block } from "../../model";
import { useBuilder } from "../../context";
import { usePhone } from "../phone";

/** Image, Link (EmbeddedLink), Photo (PhotoPicker) and Document (DocumentPicker). */
const props = defineProps<{ block: Block }>();

const { chrome } = useBuilder();
const phone = usePhone();

const component = computed(() => props.block.component);
const type = computed(() => String(component.value.type));
const image = computed(() => {
	const src = component.value.src;
	if (typeof src !== "string" || !src) return "";
	return src.startsWith("data:") || src.startsWith("http")
		? src
		: `data:image/png;base64,${src}`;
});
const imageStyle = computed(() => ({
	height: component.value.height ? `${Number(component.value.height)}px` : undefined,
	aspectRatio: component.value["aspect-ratio"]
		? String(component.value["aspect-ratio"])
		: undefined,
	objectFit:
		component.value["scale-type"] === "cover" ? ("cover" as const) : ("contain" as const),
}));
const picker = computed(() =>
	type.value === "PhotoPicker"
		? { icon: "lucide-camera", text: chrome.value.phoneAddPhoto }
		: { icon: "lucide-file-up", text: chrome.value.phoneAddDocument }
);
</script>

<template>
	<template v-if="type === 'Image'">
		<img
			v-if="image"
			:src="image"
			:alt="phone.text(component['alt-text'])"
			class="max-h-[240px] w-full rounded-[8px]"
			:style="imageStyle"
		/>
		<div
			v-else
			class="flex h-[120px] items-center justify-center rounded-[8px] bg-[var(--wa-divider)] text-[var(--wa-ink-3)]"
		>
			<span class="lucide-image size-8" aria-hidden="true" />
		</div>
	</template>
	<p v-else-if="type === 'EmbeddedLink'" class="text-[13px] font-medium text-[var(--wa-link)]">
		{{ phone.text(component.text) }}
	</p>
	<div v-else class="flex flex-col gap-2">
		<div class="flex flex-col">
			<p class="text-[13px] font-medium text-[var(--wa-ink)]">
				{{ phone.text(component.label) }}
			</p>
			<p
				v-if="component.description"
				class="text-[11px] leading-[15px] text-[var(--wa-ink-2)]"
			>
				{{ phone.text(component.description) }}
			</p>
		</div>
		<div
			class="flex h-11 items-center justify-center gap-2 rounded-[8px] border border-dashed border-[var(--wa-field)] text-[12px] font-medium text-[var(--wa-link)]"
		>
			<span class="size-4" :class="picker.icon" aria-hidden="true" />
			{{ picker.text }}
		</div>
	</div>
</template>
