<script setup lang="ts">
import { computed } from "vue";
import { useBuilder } from "../context";

/** A row's problems that belong to no single field, e.g. too few options or a duplicate answer key. */
const props = defineProps<{ screen: string; item?: string }>();
const { session } = useBuilder();

const ON_A_FIELD = ["empty-text", "empty-title", "empty-image", "text-too-long"];

const messages = computed(() =>
	session.problems.filter(
		(problem) =>
			problem.screenId === props.screen &&
			problem.blockId === props.item &&
			!ON_A_FIELD.includes(problem.code)
	)
);
</script>

<template>
	<ul v-if="messages.length" class="flex flex-col gap-1">
		<li
			v-for="problem in messages"
			:key="problem.code + problem.path"
			class="flex items-start gap-1.5 text-p-sm"
			:class="problem.severity === 'error' ? 'text-ink-red-5' : 'text-ink-amber-6'"
		>
			<span class="lucide-triangle-alert mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ problem.message }}
		</li>
	</ul>
</template>
