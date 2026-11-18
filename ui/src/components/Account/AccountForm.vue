<script setup lang="ts">
import { computed, provide } from "vue";
import { Badge, ErrorMessage } from "frappe-ui";
import { CommitKey, FormLayout, NO_COMMIT } from "@framework/ui/components/FormLayout";
import AppendActionsTable from "./AppendActionsTable.vue";
import ConnectWithMetaButton from "./ConnectWithMetaButton.vue";
import { useMetaConnect } from "./useMetaConnect";
import { accountLayout } from "./accountLayout";
import { serverErrorMessage } from "../../utils/serverError";
import type { AccountFormProps } from "./types";

const props = withDefaults(defineProps<AccountFormProps>(), { showAppendActions: true });

defineSlots<{
	/** host settings, rendered in the Settings section under Auto Send Read Receipts */
	settings?: (props: { doc: AccountFormProps["controller"]["doc"] }) => unknown;
}>();

provide(CommitKey, NO_COMMIT);

const layout = accountLayout(props.controller);

const meta = useMetaConnect();

const errorMessage = computed(() => serverErrorMessage(props.controller.error));
</script>

<template>
	<div class="flex flex-col text-ink-gray-8">
		<div
			v-if="controller.isNew && meta.canConnect"
			class="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-outline-gray-2 p-4"
			data-testid="whatsapp-connect-with-meta"
		>
			<div class="grow basis-64 text-p-sm text-ink-gray-6">
				Sign in with Meta to pick a business number, or enter the details below.
			</div>
			<ConnectWithMetaButton variant="solid" />
		</div>
		<div
			v-else-if="controller.doc.status === 'Disconnected'"
			class="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-outline-gray-2 p-4"
			data-testid="whatsapp-account-disconnected"
		>
			<div class="flex grow basis-64 flex-col gap-1.5">
				<Badge theme="red" variant="subtle" label="Disconnected" class="self-start" />
				<div class="text-p-sm text-ink-gray-6">
					Meta no longer accepts this account's access token.
					{{
						meta.canConnect
							? "Reconnect to send and receive messages again."
							: "Enter a new access token below."
					}}
				</div>
			</div>
			<ConnectWithMetaButton :account="controller.doc.name" variant="solid" />
		</div>
		<FormLayout v-model:doc="controller.doc" :layout="layout" />
		<div v-if="$slots.settings" class="flex flex-col gap-4">
			<slot name="settings" :doc="controller.doc" />
		</div>

		<div v-if="showAppendActions" class="mt-5 border-t border-outline-elevation-2 pt-5">
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
