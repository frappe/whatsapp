<script setup lang="ts">
import { computed, h } from "vue";
import { Button, Dropdown, toast, type DropdownOptions } from "frappe-ui";
import { serialize } from "../model";
import { useBuilder } from "../context";
import type { PreviewSettings } from "../types";

/** Copy Flow JSON and ⚙ ▾, as in Meta's playground, plus Edit JSON. Copy works with problems too. */
defineProps<{ compact?: boolean }>();
const emit = defineEmits<{ editJson: [] }>();
const { session, chrome } = useBuilder();

const check = () =>
	h("span", { class: "lucide-check size-4 text-ink-gray-7", "aria-hidden": "true" });

function choice<K extends "theme">(
	key: K,
	value: PreviewSettings[K],
	label: string,
	icon: string
) {
	const selected = session.preview[key] === value;
	return {
		label,
		icon,
		selected,
		slots: selected ? { suffix: check } : undefined,
		onClick: () => session.setPreview({ [key]: value }),
	};
}

const options = computed<DropdownOptions>(() => [
	{
		group: "mode",
		hideLabel: true,
		options: [
			{
				label: chrome.value.interactiveMode,
				switch: true,
				switchValue: session.preview.interactive,
				onClick: (on: boolean) => session.setPreview({ interactive: on }),
			},
		],
	},
	{
		group: chrome.value.theme,
		options: [
			choice("theme", "light", chrome.value.light, "lucide-sun"),
			choice("theme", "dark", chrome.value.dark, "lucide-moon"),
		],
	},
	{
		group: "json",
		hideLabel: true,
		options: [
			{
				label: chrome.value.editJson,
				icon: "lucide-braces",
				onClick: () => emit("editJson"),
			},
		],
	},
]);

async function copy() {
	try {
		await navigator.clipboard.writeText(JSON.stringify(serialize(session.model!), null, 2));
		toast.success(chrome.value.jsonCopied);
	} catch {
		toast.error(chrome.value.copyFailed);
	}
}
</script>

<template>
	<div class="flex shrink-0 items-center gap-2">
		<Button
			v-if="compact"
			variant="outline"
			icon="lucide-copy"
			:aria-label="chrome.copyJson"
			@click="copy"
		/>
		<Button
			v-else
			variant="outline"
			icon-left="lucide-copy"
			:label="chrome.copyJson"
			@click="copy"
		/>
		<Dropdown :options="options" align="end">
			<Button
				variant="outline"
				icon-left="lucide-settings"
				icon-right="lucide-chevron-down"
				:aria-label="chrome.previewSettings"
			/>
		</Dropdown>
	</div>
</template>
