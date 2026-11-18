<script setup lang="ts">
import { computed } from "vue";
import { Tooltip } from "frappe-ui";
import type { FlowAnswersProps } from "./types";

const props = withDefaults(defineProps<FlowAnswersProps>(), {
	answers: () => [],
	submittedLabel: "Form submitted",
	sensitiveLabel: "Hidden: the form marks this answer as sensitive",
	yesLabel: "Yes",
	noLabel: "No",
	oneFileLabel: "1 file",
	filesLabel: "{0} files",
});

const EMPTY = "—";

const rows = computed(() =>
	props.answers.map((answer) => ({
		...answer,
		text: answer.masked ? "" : display(answer.value),
	}))
);

function display(value: unknown): string {
	if (value === null || value === undefined || value === "") return EMPTY;
	if (typeof value === "boolean") return value ? props.yesLabel : props.noLabel;
	if (Array.isArray(value)) return displayList(value);
	if (typeof value === "object") return isMedia(value) ? fileCount(1) : displayObject(value);
	return String(value);
}

function displayList(values: unknown[]): string {
	if (!values.length) return EMPTY;
	if (values.every(isMedia)) return fileCount(values.length);
	return values.map(display).join(", ");
}

function displayObject(value: object): string {
	const parts = Object.values(value).filter((part) => part !== null && part !== "");
	return parts.length ? parts.map(display).join(", ") : EMPTY;
}

/** Meta sends each photo or document a customer picked as an object naming its media. */
function isMedia(value: unknown): boolean {
	return (
		typeof value === "object" && value !== null && ("media_id" in value || "cdn_url" in value)
	);
}

function fileCount(count: number): string {
	return count === 1 ? props.oneFileLabel : props.filesLabel.replace("{0}", String(count));
}
</script>

<template>
	<div class="flex flex-col gap-1.5">
		<div v-if="flowName" class="text-sm font-medium text-ink-gray-7">{{ flowName }}</div>

		<div v-if="!answers.length" class="text-ink-gray-7">{{ submittedLabel }}</div>

		<!-- a fixed label lane, so every value starts on the same line however long its label -->
		<dl v-else class="grid grid-cols-[7rem_minmax(0,1fr)] items-baseline gap-x-3 gap-y-1">
			<template v-for="answer in rows" :key="answer.key">
				<dt class="break-words text-p-sm text-ink-gray-6">{{ answer.label }}</dt>
				<dd v-if="answer.masked" class="flex items-center gap-1.5">
					<span class="tracking-[0.2em] text-ink-gray-7" aria-hidden="true">••••••</span>
					<Tooltip :text="sensitiveLabel">
						<span
							class="lucide-lock size-3.5 shrink-0 text-ink-gray-6"
							role="img"
							:aria-label="sensitiveLabel"
						/>
					</Tooltip>
				</dd>
				<dd
					v-else
					class="whitespace-pre-line break-words text-p-base"
					:class="answer.text === EMPTY ? 'text-ink-gray-6' : 'text-ink-gray-9'"
				>
					{{ answer.text }}
				</dd>
			</template>
		</dl>
	</div>
</template>
