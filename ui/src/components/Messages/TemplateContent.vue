<!-- eslint-disable vue/no-v-html -->
<script setup lang="ts">
import TemplateButtons from "./TemplateButtons.vue";
import { formatWhatsAppMessage } from "../../utils/formatMessage";
import type { TemplateContentProps } from "./types";

defineProps<TemplateContentProps>();
</script>

<template>
	<div class="flex flex-col gap-2">
		<div v-if="header" class="text-base font-semibold">{{ header }}</div>
		<div :class="bodyClass" v-html="formatWhatsAppMessage(body)" />
		<div v-if="footer" class="text-xs text-ink-gray-5">{{ footer }}</div>
		<TemplateButtons :buttons="buttons" />
	</div>
</template>
