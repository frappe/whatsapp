<!-- eslint-disable vue/no-v-html -->
<script setup lang="ts">
import TemplateButtons from "./TemplateButtons.vue";
import { formatWhatsAppMessage } from "../../utils/formatMessage";
import type { TemplateContentProps } from "./types";

defineProps<TemplateContentProps>();
</script>

<template>
	<div class="flex flex-col gap-2">
		<!-- `font-bold`, matching what `<b>` resolves to: the header is part of the message the
		     recipient reads, not chrome, so it carries the same weight as emphasis in a body -->
		<div v-if="header" class="text-base font-bold">{{ header }}</div>
		<div :class="bodyClass" v-html="formatWhatsAppMessage(body)" />
		<div v-if="footer" class="text-xs text-ink-gray-6">{{ footer }}</div>
		<TemplateButtons :buttons="buttons" />
	</div>
</template>
