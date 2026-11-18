<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { TextInput, Textarea } from "frappe-ui";
import { format } from "../chrome";
import { useBuilder } from "../context";

/**
 * A text field with Meta's `n/max` counter inside it. `maxlength` stops typing at the limit, so
 * the counter never needs a line of its own.
 */
const props = defineProps<{
	modelValue: string;
	limit?: number;
	label?: string;
	/** Adds Meta's muted "· Optional" to the label. */
	optional?: boolean;
	description?: string;
	error?: string;
	multiline?: boolean;
	placeholder?: string;
}>();
const emit = defineEmits<{ "update:modelValue": [value: string]; blur: [] }>();

const { session, chrome } = useBuilder();

const counter = computed(() =>
	props.limit ? format(chrome.value.counter, props.modelValue.length, props.limit) : ""
);
const over = computed(() => !!props.limit && props.modelValue.length > props.limit);
const counterWidth = computed(() => `${String(props.limit ?? "").length * 2 + 1}ch`);

const area = ref<InstanceType<typeof Textarea>>();
const input = ref<InstanceType<typeof TextInput>>();
const counterTop = ref(0);

/** The textarea's own label sits above it; the counter goes inside the box, below the label. */
async function placeCounter() {
	await nextTick();
	counterTop.value = area.value?.inputElement?.offsetTop ?? 0;
}
onMounted(placeCounter);
watch(() => props.label, placeCounter);

function update(value: unknown) {
	emit("update:modelValue", String(value ?? ""));
}

defineExpose({
	focus: () => (area.value ?? input.value)?.focus(),
	select: () => (area.value?.inputElement ?? input.value?.inputElement)?.select(),
});
</script>

<template>
	<div v-if="multiline" class="fb-counted relative" :style="{ '--fb-counter': counterWidth }">
		<Textarea
			ref="area"
			:label="label"
			:description="description"
			:error="error"
			:model-value="modelValue"
			:placeholder="placeholder"
			:maxlength="limit"
			:rows="3"
			:disabled="session.readOnly"
			@update:model-value="update"
			@blur="emit('blur')"
		>
			<template v-if="optional" #label>
				{{ label }} <span class="text-ink-gray-5">· {{ chrome.optional }}</span>
			</template>
		</Textarea>
		<span
			v-if="limit"
			class="pointer-events-none absolute right-2 pt-1.5 text-sm tabular-nums"
			:class="over || error ? 'text-ink-red-5' : 'text-ink-gray-5'"
			:style="{ top: `${counterTop}px` }"
			aria-hidden="true"
		>
			{{ counter }}
		</span>
	</div>
	<TextInput
		v-else
		ref="input"
		class="fb-counted"
		:style="{ '--fb-counter': counterWidth }"
		:label="label"
		:description="description"
		:error="error"
		:model-value="modelValue"
		:placeholder="placeholder"
		:maxlength="limit"
		:disabled="session.readOnly"
		@update:model-value="update"
		@blur="emit('blur')"
	>
		<template v-if="optional" #label>
			{{ label }} <span class="text-ink-gray-5">· {{ chrome.optional }}</span>
		</template>
		<template v-if="limit" #suffix>
			<span
				class="text-sm tabular-nums"
				:class="over || error ? 'text-ink-red-5' : 'text-ink-gray-5'"
				aria-hidden="true"
			>
				{{ counter }}
			</span>
		</template>
	</TextInput>
</template>

<style>
.fb-counted input,
.fb-counted textarea {
	padding-inline-end: calc(var(--fb-counter) + 0.75rem) !important;
}
</style>
