<script setup lang="ts">
import { computed } from "vue";
import type { Block } from "../../model";
import { format } from "../../chrome";
import { useBuilder } from "../../context";
import { usePhoneBlock } from "../phone";
import PhoneField from "./PhoneField.vue";

/** Short answer (TextInput) and Paragraph (TextArea). */
const props = defineProps<{ block: Block }>();

const { chrome } = useBuilder();
const { phone, component, name, text: value } = usePhoneBlock(props);

const TEXTAREA_MAX = 600;
const INPUT_TYPES: Record<string, { type: string; inputmode?: "numeric" | "email" | "tel" }> = {
	password: { type: "password" },
	passcode: { type: "password", inputmode: "numeric" },
	email: { type: "email", inputmode: "email" },
	number: { type: "text", inputmode: "numeric" },
	phone: { type: "tel", inputmode: "tel" },
};

const multiline = computed(() => component.value.type === "TextArea");
const input = computed(
	() => INPUT_TYPES[String(component.value["input-type"] ?? "")] ?? { type: "text" }
);
const max = computed(() => Number(component.value["max-length"]) || TEXTAREA_MAX);

function type(event: Event) {
	phone.run.set(name.value, (event.target as HTMLInputElement).value);
}
</script>

<template>
	<PhoneField
		:label="phone.text(component.label)"
		:required="component.required === true"
		:filled="!!value"
		:helper="phone.text(component['helper-text'])"
		:tall="multiline"
	>
		<textarea
			v-if="multiline"
			class="h-[64px] w-full resize-none border-0 bg-transparent p-0 text-[13px] text-[var(--wa-ink)] focus:outline-none focus:ring-0"
			:value="value"
			:maxlength="max"
			@input="type"
		/>
		<input
			v-else
			class="w-full border-0 bg-transparent p-0 text-[13px] text-[var(--wa-ink)] focus:outline-none focus:ring-0"
			:type="input.type"
			:inputmode="input.inputmode"
			:value="value"
			@input="type"
		/>
		<template v-if="multiline" #after>
			<span class="shrink-0 tabular-nums">{{
				format(chrome.phoneCounter, value.length, max)
			}}</span>
		</template>
	</PhoneField>
</template>
