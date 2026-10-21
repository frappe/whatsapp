<script setup lang="ts">
import { computed, provide } from "vue";
import { ErrorMessage } from "frappe-ui";
import { CommitKey, FormLayout, NO_COMMIT } from "@framework/ui/components/FormLayout";
import AppendActionsTable from "./AppendActionsTable.vue";
import { accountLayout } from "./accountLayout";
import { serverErrorMessage } from "../../utils/serverError";
import type { AccountFormProps } from "./types";

const props = defineProps<AccountFormProps>();

provide(CommitKey, NO_COMMIT);

const layout = accountLayout(props.controller);

const errorMessage = computed(() => serverErrorMessage(props.controller.error));
</script>

<template>
	<div class="flex flex-col text-ink-gray-8">
		<FormLayout v-model:doc="controller.doc" :layout="layout" />

		<div class="mt-5 border-t border-outline-elevation-2 pt-5">
			<div class="text-base-medium text-ink-gray-9">Append Actions</div>
			<div class="mt-6">
				<AppendActionsTable :controller="controller" />
				<div class="mt-2 text-xs text-ink-gray-5">
					Auto-create documents in linked DocTypes when messages are received or sent
				</div>
			</div>
		</div>

		<ErrorMessage class="mt-4" :message="errorMessage" />
	</div>
</template>
