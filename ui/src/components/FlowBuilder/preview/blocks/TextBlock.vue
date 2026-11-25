<script setup lang="ts">
import { computed } from "vue";
import type { Block } from "../../model";
import { usePhone } from "../phone";

/** Large heading, Small heading, Body, Caption and Rich text. */
const props = defineProps<{ block: Block }>();
const phone = usePhone();

const STYLES: Record<string, string> = {
	TextHeading: "text-[18px] leading-[24px] font-semibold",
	TextSubheading: "text-[15px] leading-[20px] font-semibold",
	TextBody: "text-[13px] leading-[18px]",
	TextCaption: "text-[11px] leading-[15px] text-[var(--wa-ink-2)]",
};

const component = computed(() => props.block.component);
const type = computed(() => String(component.value.type));
const style = computed(() => STYLES[type.value] ?? STYLES.TextBody);
const emphasis = computed(() => [
	component.value["font-weight"] === "bold" && "font-bold",
	component.value["font-weight"] === "italic" && "italic",
	component.value["font-weight"] === "bold_italic" && "font-bold italic",
	component.value.strikethrough === true && "line-through",
]);

/** Rich text is Markdown; the preview draws its headings and bullets and drops the other marks. */
const lines = computed(() => {
	const text = component.value.text;
	const all = (Array.isArray(text) ? text.map(String) : String(text ?? "").split("\n")).map(
		(line) => phone.text(line)
	);
	return all.filter((line) => line.trim()).map(richLine);
});

function richLine(line: string): { kind: string; text: string } {
	const plain = line.replace(/\*\*|__|~~|`/g, "");
	if (/^#\s/.test(plain)) return { kind: "TextHeading", text: plain.replace(/^#\s+/, "") };
	if (/^#{2,}\s/.test(plain))
		return { kind: "TextSubheading", text: plain.replace(/^#+\s+/, "") };
	if (/^\s*([-*+]|\d+\.)\s/.test(plain))
		return { kind: "bullet", text: plain.replace(/^\s*([-*+]|\d+\.)\s+/, "") };
	return { kind: "TextBody", text: plain };
}
</script>

<template>
	<div v-if="type === 'RichText'" class="flex flex-col gap-2 text-[var(--wa-ink)]">
		<template v-for="(line, index) in lines" :key="index">
			<p v-if="line.kind === 'bullet'" :class="STYLES.TextBody" class="flex gap-2">
				<span aria-hidden="true">•</span><span>{{ line.text }}</span>
			</p>
			<p v-else :class="STYLES[line.kind]">{{ line.text }}</p>
		</template>
	</div>
	<p v-else class="whitespace-pre-line text-[var(--wa-ink)]" :class="[style, ...emphasis]">
		{{ phone.text(component.text) }}
	</p>
</template>
