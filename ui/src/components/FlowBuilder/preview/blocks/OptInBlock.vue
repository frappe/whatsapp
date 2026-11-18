<script setup lang="ts">
import { computed } from "vue";
import type { Block, JsonObject } from "../../model";
import { useBuilder } from "../../context";
import { usePhoneBlock } from "../phone";
import PhoneCheck from "./PhoneCheck.vue";

/** Opt-in: a checkbox and its text, with "Read more" when it opens a screen or a link. */
const props = defineProps<{ block: Block }>();

const { chrome } = useBuilder();
const { phone, component, name, answer } = usePhoneBlock(props);

const on = computed(() => answer.value === true);
const link = computed(() => component.value["on-click-action"] as JsonObject | undefined);

function readMore() {
	if (phone.settings.interactive && link.value?.name === "navigate")
		phone.run.readMore(props.block.uid);
}
</script>

<template>
	<div class="flex items-start gap-3 py-1">
		<button
			type="button"
			role="checkbox"
			:aria-checked="on"
			class="pt-px"
			@click="phone.run.set(name, !on)"
		>
			<PhoneCheck shape="square" :on="on" />
		</button>
		<p class="min-w-0 flex-1 text-[13px] leading-[18px] text-[var(--wa-ink)]">
			{{ phone.text(component.label) }}
			<button
				v-if="link"
				type="button"
				class="font-medium text-[var(--wa-link)]"
				@click="readMore"
			>
				{{ chrome.phoneReadMore }}
			</button>
		</p>
	</div>
</template>
