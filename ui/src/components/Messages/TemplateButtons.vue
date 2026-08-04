<script setup lang="ts">
import { FeatherIcon } from "frappe-ui";
import type { TemplateButtonsProps, WhatsAppTemplateButton } from "./types";

withDefaults(defineProps<TemplateButtonsProps>(), {
	buttons: () => [],
});

function iconForButtonType(type: WhatsAppTemplateButton["button_type"]): string {
	switch (type) {
		case "URL":
			return "external-link";
		case "PHONE_NUMBER":
		case "VOICE_CALL":
			return "phone";
		case "COPY_CODE":
			return "copy";
		case "QUICK_REPLY":
			return "corner-up-left";
		default:
			return "";
	}
}
</script>

<template>
	<div v-if="buttons?.length" class="-mx-2 -mb-1.5 mt-1 flex flex-col">
		<div
			v-for="(btn, i) in buttons"
			:key="i"
			class="flex items-center justify-center gap-1.5 border-t border-outline-gray-2 py-2 text-sm text-ink-blue-link"
		>
			<FeatherIcon
				v-if="iconForButtonType(btn.button_type)"
				:name="iconForButtonType(btn.button_type)"
				class="size-3.5"
			/>
			{{ btn.button_text }}
		</div>
	</div>
</template>
