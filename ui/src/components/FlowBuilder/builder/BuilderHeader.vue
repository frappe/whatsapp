<script setup lang="ts">
import { computed } from "vue";
import { Badge, Button, Tooltip } from "frappe-ui";
import { format } from "../chrome";
import { useBuilder } from "../context";
import { STATUS_THEME } from "../status";
import { firstProblem } from "./problems";
import { serverErrorMessage } from "../../../utils/serverError";

defineProps<{ publishing: boolean }>();
const emit = defineEmits<{ close: []; publish: [] }>();

const { session, chrome, rows } = useBuilder();

const problemCount = computed(() => session.problems.length);
const problemLabel = computed(() =>
	problemCount.value === 1
		? chrome.value.oneProblem
		: format(chrome.value.problems, problemCount.value)
);

const publishReason = computed(() => {
	const count = session.errorCount;
	if (!count) return "";
	return count === 1
		? chrome.value.publishBlockedError
		: format(chrome.value.publishBlockedErrors, count);
});
</script>

<template>
	<header class="flex h-12 shrink-0 items-center gap-3 border-b border-outline-gray-1 px-3">
		<nav class="flex min-w-0 items-center gap-1 text-lg" aria-label="Breadcrumbs">
			<Button
				variant="ghost"
				:label="chrome.flowsCrumb"
				class="shrink-0 text-ink-gray-5"
				@click="emit('close')"
			/>
			<span class="shrink-0 text-ink-gray-4" aria-hidden="true">/</span>
			<span class="truncate px-1 text-base-medium text-ink-gray-9">{{
				session.flow?.flow_name
			}}</span>
		</nav>
		<Badge
			v-if="session.flow && session.flow.status !== 'Draft'"
			class="shrink-0"
			variant="subtle"
			:theme="STATUS_THEME[session.flow.status]"
			:label="chrome[session.flow.status]"
		/>
		<span
			v-if="!session.readOnly"
			class="flex w-44 shrink-0 items-center gap-1 text-sm text-ink-gray-5"
			role="status"
		>
			<template v-if="session.saveState === 'failed'">
				<span class="text-ink-red-7" :title="serverErrorMessage(session.saveError)">{{
					chrome.saveFailed
				}}</span>
				<span aria-hidden="true">·</span>
				<Button
					variant="ghost"
					theme="red"
					size="sm"
					:label="chrome.retry"
					@click="session.save()"
				/>
			</template>
			<template v-else-if="session.saveState === 'saving'">{{ chrome.saving }}</template>
		</span>
		<div class="flex-1" />
		<span class="flex w-14 shrink-0 justify-end">
			<Button
				v-if="problemCount"
				variant="ghost"
				:theme="session.errorCount ? 'red' : 'gray'"
				:aria-label="problemLabel"
				@click="rows.revealProblem(firstProblem(session.model!, session.problems)!)"
			>
				<template #prefix>
					<span
						class="lucide-triangle-alert size-4"
						:class="!session.errorCount && 'text-ink-amber-5'"
						aria-hidden="true"
					/>
				</template>
				{{ problemCount }}
			</Button>
		</span>
		<Tooltip v-if="!session.readOnly" :text="publishReason" :disabled="!publishReason">
			<span class="shrink-0" :tabindex="publishReason ? 0 : undefined">
				<Button
					variant="solid"
					:label="chrome.publish"
					:loading="publishing"
					:disabled="!!publishReason || session.conflict"
					@click="emit('publish')"
				/>
			</span>
		</Tooltip>
	</header>
</template>
