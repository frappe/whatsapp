<script setup lang="ts">
import { computed, type Component } from "vue";
import { kindOf, type Block } from "../model";
import { useBuilder } from "../context";
import { usePhone } from "./phone";
import ChipsBlock from "./blocks/ChipsBlock.vue";
import ChoiceBlock from "./blocks/ChoiceBlock.vue";
import DateBlock from "./blocks/DateBlock.vue";
import DropdownBlock from "./blocks/DropdownBlock.vue";
import InputBlock from "./blocks/InputBlock.vue";
import MediaBlock from "./blocks/MediaBlock.vue";
import OptInBlock from "./blocks/OptInBlock.vue";
import TextBlock from "./blocks/TextBlock.vue";

/**
 * One component on the phone. Outside Interactive mode a click picks it (its row opens on the
 * left), and the one being edited gets a gray ring.
 */
const props = defineProps<{ block: Block }>();

const RENDERERS: Record<string, Component> = {
	TextHeading: TextBlock,
	TextSubheading: TextBlock,
	TextBody: TextBlock,
	TextCaption: TextBlock,
	RichText: TextBlock,
	TextInput: InputBlock,
	TextArea: InputBlock,
	DatePicker: DateBlock,
	CalendarPicker: DateBlock,
	RadioButtonsGroup: ChoiceBlock,
	CheckboxGroup: ChoiceBlock,
	ChipsSelector: ChipsBlock,
	Dropdown: DropdownBlock,
	OptIn: OptInBlock,
	Image: MediaBlock,
	EmbeddedLink: MediaBlock,
	PhotoPicker: MediaBlock,
	DocumentPicker: MediaBlock,
};

const { chrome } = useBuilder();
const phone = usePhone();

const renderer = computed(() =>
	kindOf(props.block) ? RENDERERS[String(props.block.component.type)] : undefined
);
const picking = computed(() => !phone.settings.interactive);
const ringed = computed(() => picking.value && phone.highlight === props.block.uid);
</script>

<template>
	<div
		v-if="block.component.visible !== false"
		:data-block="block.uid"
		class="fb-phone-block rounded-[6px] transition-[outline-color] duration-150"
		:class="[picking && 'fb-phone-pickable', ringed && 'fb-phone-ringed']"
		@click.capture="picking && phone.pick(block.uid)"
	>
		<component :is="renderer" v-if="renderer" :block="block" />
		<div
			v-else
			class="flex flex-col gap-0.5 rounded-[8px] border border-dashed border-[var(--wa-field)] px-3 py-2.5 text-[11px] text-[var(--wa-ink-3)]"
		>
			<span>{{ chrome.shownInWhatsApp }}</span>
			<span class="font-mono text-[10px]">{{ block.component.type ?? "?" }}</span>
		</div>
	</div>
</template>

<style>
.fb-phone-block {
	outline: 2px solid transparent;
	outline-offset: 4px;
}
.fb-phone-pickable {
	cursor: pointer;
}
.fb-phone-pickable:hover {
	outline-color: var(--outline-gray-2);
}
.fb-phone-ringed,
.fb-phone-ringed:hover {
	outline-color: var(--outline-gray-4);
}
@media (prefers-reduced-motion: reduce) {
	.fb-phone-block {
		transition: none;
	}
}
</style>
