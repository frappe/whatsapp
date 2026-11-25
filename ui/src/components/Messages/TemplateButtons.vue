<script setup lang="ts">
import type { Component } from "vue";
import LucideClipboardList from "~icons/lucide/clipboard-list";
import LucideCopy from "~icons/lucide/copy";
import LucideCornerUpLeft from "~icons/lucide/corner-up-left";
import LucideExternalLink from "~icons/lucide/external-link";
import LucidePhone from "~icons/lucide/phone";
import { FLOW_ICONS } from "./flowIcons";
import type { TemplateButtonsProps, WhatsAppTemplateButton } from "./types";

withDefaults(defineProps<TemplateButtonsProps>(), {
	buttons: () => [],
});

// Imported components, not `lucide-*` classes: the icon is picked at runtime, and Tailwind
// only emits CSS for class names it can read as complete strings in the source.
const BUTTON_TYPE_ICONS: Record<WhatsAppTemplateButton["button_type"], Component> = {
	URL: LucideExternalLink,
	"Phone Number": LucidePhone,
	"Voice Call": LucidePhone,
	"Copy Code": LucideCopy,
	"Quick Reply": LucideCornerUpLeft,
	Flow: LucideClipboardList,
};

function iconFor(button: WhatsAppTemplateButton): Component | undefined {
	const flowIcon =
		button.button_type === "Flow" && button.flow_icon ? FLOW_ICONS[button.flow_icon] : undefined;
	return flowIcon ?? BUTTON_TYPE_ICONS[button.button_type];
}
</script>

<template>
	<!-- display only: this is what WhatsApp will draw on the recipient's phone, so nothing
	     here is clickable and none of it is announced as an interactive control -->
	<div v-if="buttons?.length" role="presentation" class="-mx-2.5 -mb-1.5 mt-1 flex flex-col">
		<div
			v-for="(btn, i) in buttons"
			:key="i"
			class="flex items-center justify-center gap-1.5 border-t border-outline-gray-2 py-2 text-sm text-ink-gray-7"
		>
			<component :is="iconFor(btn)" v-if="iconFor(btn)" class="size-3.5" />
			{{ btn.button_text }}
		</div>
	</div>
</template>
