<script setup lang="ts">
import { computed, h } from "vue";
import { Button, Dropdown, Tooltip } from "frappe-ui";
import {
	BLOCK_KINDS,
	SCREEN_LIMITS,
	addBlock,
	screenItems,
	updateBlock,
	type Screen,
} from "../model";
import { objects } from "../model/edit";
import { format } from "../chrome";
import { useBuilder } from "../context";
import { CONTENT_MENU } from "./describe";

/** Meta's "Add content" menu. A new component goes just before the Button. */
const props = defineProps<{ screen: Screen }>();
const emit = defineEmits<{ added: [uid: string] }>();
const { session, chrome, edit } = useBuilder();

/** Meta turns Required on for a new question. */
const REQUIRED_BY_DEFAULT = [
	"TextInput",
	"TextArea",
	"DatePicker",
	"CalendarPicker",
	"RadioButtonsGroup",
	"CheckboxGroup",
	"Dropdown",
	"ChipsSelector",
	"OptIn",
];

/** Every component on the screen, nested ones included, as Meta counts them. */
const types = computed(() =>
	screenItems(props.screen).flatMap((item) =>
		[...objects(item.component)]
			.map((object) => object.type)
			.filter((type) => typeof type === "string")
	)
);
const full = computed(() =>
	types.value.length >= SCREEN_LIMITS.components
		? format(chrome.value.maxComponents, SCREEN_LIMITS.components)
		: ""
);

function limitReason(type: string): string {
	const limit = SCREEN_LIMITS[type as keyof typeof SCREEN_LIMITS];
	if (!limit || type === "components") return "";
	return types.value.filter((each) => each === type).length >= limit
		? format(chrome.value.maxOnScreen, limit)
		: "";
}

const menu = computed(() =>
	CONTENT_MENU.map(({ group, icon, types: groupTypes }) => ({
		label: chrome.value[group],
		icon,
		submenu: groupTypes.map((type) => {
			const reason = limitReason(type);
			const label = chrome.value[type];
			return {
				label,
				disabled: !!reason,
				slots: reason
					? {
							label: () =>
								h(Tooltip, { text: reason, side: "right" }, () =>
									h("span", label)
								),
					  }
					: undefined,
				onClick: () => add(type),
			};
		}),
	}))
);

function add(type: string) {
	const kind = BLOCK_KINDS[type];
	const text = kind.question
		? chrome.value.labelLabel
		: kind.textKey === "text"
		? chrome.value.textLabel
		: "";
	let uid = "";
	edit((model) => {
		const added = addBlock(model, props.screen.uid, type, { text });
		uid = added.uid;
		return REQUIRED_BY_DEFAULT.includes(type)
			? updateBlock(added.model, uid, { required: true })
			: added.model;
	});
	if (uid) emit("added", uid);
}
</script>

<template>
	<Tooltip :text="full" :disabled="!full">
		<span class="self-start" :tabindex="full ? 0 : undefined">
			<Dropdown :options="menu">
				<Button
					variant="subtle"
					icon-left="lucide-plus"
					icon-right="lucide-chevron-down"
					:label="chrome.addContent"
					:disabled="!!full || session.readOnly"
				/>
			</Dropdown>
		</span>
	</Tooltip>
</template>
