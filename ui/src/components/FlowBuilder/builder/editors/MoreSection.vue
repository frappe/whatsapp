<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Switch, TextInput, Tooltip } from "frappe-ui";
import {
	OPTION_LIMITS,
	isSensitive,
	kindOf,
	prefillKey,
	setSensitive,
	updateOption,
	type Block,
	type JsonObject,
	type Screen,
} from "../../model";
import { format } from "../../chrome";
import CountedInput from "../CountedInput.vue";
import { useBlock } from "./useBlock";

/** Our additions to Meta's fields: answer key, Hide in chat, prefill, option ids and descriptions. */
const props = defineProps<{ block: Block; screen: Screen }>();
const { session, chrome, edit, actions, component, type, value, set } = useBlock(props);

const NO_PREFILL = ["PhotoPicker", "DocumentPicker"];
const WITH_DESCRIPTION = ["RadioButtonsGroup", "CheckboxGroup", "ChipsSelector"];

const question = computed(() => !!kindOf(props.block)?.question);
const options = computed(() => component.value["data-source"] as JsonObject[] | undefined);
const key = computed(() => value("name"));
const draftKey = ref(key.value);
watch(key, (next) => (draftKey.value = next));

const usedBy = computed(() => session.usedKey(key.value).length);
const keyDescription = computed(() => {
	if (!usedBy.value) return chrome.value.answerKeyHint;
	return usedBy.value === 1
		? chrome.value.usedByTemplate
		: format(chrome.value.usedByTemplates, usedBy.value);
});
const firstScreen = computed(() => session.model!.screens[0]?.uid === props.screen.uid);
const prefilled = computed(() => !!prefillKey(props.screen, props.block));

function commitKey() {
	actions.renameKey(props.block, draftKey.value.trim(), () => (draftKey.value = key.value));
}
</script>

<template>
	<div class="flex flex-col gap-4 border-t border-outline-gray-1 pt-4">
		<template v-if="question">
			<TextInput
				v-model="draftKey"
				:label="chrome.answerKeyLabel"
				:description="keyDescription"
				:disabled="session.readOnly"
				@blur="commitKey"
				@keydown.enter="($event.target as HTMLInputElement).blur()"
			/>
			<Switch
				:label="chrome.sensitiveLabel"
				:description="chrome.sensitiveHint"
				:model-value="isSensitive(screen, block)"
				:disabled="session.readOnly"
				@update:model-value="
					(on) => edit((model) => setSensitive(model, block.uid, on === true))
				"
			/>
			<Tooltip
				v-if="!NO_PREFILL.includes(type)"
				:text="chrome.prefillFirstScreen"
				:disabled="firstScreen || prefilled"
			>
				<div :tabindex="firstScreen || prefilled ? undefined : 0">
					<Switch
						:label="chrome.prefillLabel"
						:description="chrome.prefillHint"
						:model-value="prefilled"
						:disabled="session.readOnly || (!firstScreen && !prefilled)"
						@update:model-value="
							(on) => actions.setPrefill(screen, block, on === true)
						"
					/>
				</div>
			</Tooltip>
		</template>
		<CountedInput
			v-if="type === 'Image'"
			:label="chrome.altTextLabel"
			:model-value="value('alt-text')"
			@update:model-value="(next) => set('alt-text', next)"
		/>
		<div v-if="options?.length" class="flex flex-col gap-2">
			<p class="text-sm leading-tighter text-ink-gray-6">{{ chrome.optionIdsLabel }}</p>
			<div
				v-for="(option, index) in options"
				:key="`${option.id}:${index}`"
				class="flex items-center gap-2"
			>
				<span
					class="w-28 shrink-0 truncate font-mono text-sm text-ink-gray-5"
					:title="String(option.id)"
				>
					{{ option.id }}
				</span>
				<CountedInput
					v-if="WITH_DESCRIPTION.includes(type)"
					class="min-w-0 flex-1"
					:aria-label="`${chrome.optionDescription}: ${option.title}`"
					:placeholder="chrome.optionDescription"
					:limit="OPTION_LIMITS.description"
					:model-value="String(option.description ?? '')"
					@update:model-value="
						(next) =>
							edit((model) =>
								updateOption(model, block.uid, index, {
									description: next || undefined,
								})
							)
					"
				/>
				<span v-else class="min-w-0 flex-1 truncate text-base text-ink-gray-7">{{
					option.title
				}}</span>
			</div>
		</div>
	</div>
</template>
