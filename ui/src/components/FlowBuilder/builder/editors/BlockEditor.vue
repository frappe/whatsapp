<script setup lang="ts">
import { computed, ref, type Component } from "vue";
import { Button, Switch } from "frappe-ui";
import { deleteBlock, kindOf, type Block, type Screen } from "../../model";
import { collapse } from "../collapse";
import RowMessages from "../RowMessages.vue";
import ImageEditor from "./ImageEditor.vue";
import LinkEditor from "./LinkEditor.vue";
import MoreSection from "./MoreSection.vue";
import OptInEditor from "./OptInEditor.vue";
import OptionsEditor from "./OptionsEditor.vue";
import QuestionEditor from "./QuestionEditor.vue";
import TextEditor from "./TextEditor.vue";
import { useBlock } from "./useBlock";

/** Meta's order: the kind's fields, then More, Required and delete on one line. */
const props = defineProps<{ block: Block; screen: Screen }>();
const { session, chrome, edit, type, set } = useBlock(props);

const EDITORS: Record<string, Component[]> = {
	TextHeading: [TextEditor],
	TextSubheading: [TextEditor],
	TextBody: [TextEditor],
	TextCaption: [TextEditor],
	RichText: [TextEditor],
	Image: [ImageEditor],
	EmbeddedLink: [LinkEditor],
	OptIn: [OptInEditor],
	RadioButtonsGroup: [QuestionEditor, OptionsEditor],
	CheckboxGroup: [QuestionEditor, OptionsEditor],
	Dropdown: [QuestionEditor, OptionsEditor],
	ChipsSelector: [QuestionEditor, OptionsEditor],
};
const NOT_REQUIRED = ["PhotoPicker", "DocumentPicker"];

const more = ref(false);
const kind = computed(() => kindOf(props.block));
const editors = computed(() => EDITORS[type.value] ?? [QuestionEditor]);
const hasMore = computed(
	() => kind.value?.question || kind.value?.choices || type.value === "Image"
);
const canRequire = computed(() => kind.value?.question && !NOT_REQUIRED.includes(type.value));
</script>

<template>
	<component
		:is="editor"
		v-for="(editor, index) in editors"
		:key="index"
		:block="block"
		:screen="screen"
	/>
	<RowMessages :screen="screen.uid" :item="block.uid" />
	<div>
		<div class="flex h-7 items-center gap-2">
			<Button
				v-if="hasMore"
				variant="ghost"
				size="sm"
				:label="chrome.more"
				:icon-right="more ? 'lucide-chevron-up' : 'lucide-chevron-down'"
				:aria-expanded="more"
				@click="more = !more"
			/>
			<div class="flex-1" />
			<Switch
				v-if="canRequire"
				size="sm"
				:label="chrome.requiredLabel"
				:model-value="block.component.required === true"
				:disabled="session.readOnly"
				@update:model-value="(on) => set('required', on === true)"
			/>
			<Button
				v-if="!session.readOnly"
				variant="ghost"
				icon="lucide-trash-2"
				:aria-label="chrome.delete"
				@click="edit((model) => deleteBlock(model, block.uid))"
			/>
		</div>
		<Transition :css="false" @enter="collapse.onEnter" @leave="collapse.onLeave">
			<div v-if="more">
				<div class="pt-3">
					<MoreSection :block="block" :screen="screen" />
				</div>
			</div>
		</Transition>
	</div>
</template>
