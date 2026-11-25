<script setup lang="ts">
import { ref } from "vue";
import { Button } from "frappe-ui";

/** A trash button that turns red on the first click and deletes on the second. */
const props = defineProps<{ label: string; confirmLabel: string; disabled?: boolean }>();
const emit = defineEmits<{ confirm: [] }>();

const armed = ref(false);

function click() {
	if (!armed.value) {
		armed.value = true;
		return;
	}
	armed.value = false;
	emit("confirm");
}
</script>

<template>
	<Button
		:variant="armed ? 'subtle' : 'ghost'"
		:theme="armed ? 'red' : 'gray'"
		icon="lucide-trash-2"
		:aria-label="armed ? props.confirmLabel : props.label"
		:title="armed ? props.confirmLabel : undefined"
		:disabled="disabled"
		@click.stop="click"
		@blur="armed = false"
		@mouseleave="armed = false"
	/>
</template>
