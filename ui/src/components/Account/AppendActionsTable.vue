<script setup lang="ts">
import { Combobox, Select } from "frappe-ui";
import { Grid, type GridColumn } from "@framework/ui/components/Grid";
import { Link } from "@framework/ui/components/Link";
import { emptyAppendAction } from "./useAccount";
import type { AppendAction, AppendActionsTableProps, MappingSlot } from "./types";

const props = defineProps<AppendActionsTableProps>();

// Only documents a message can be appended to: child rows and singles have no list to add to.
const APPEND_TO_FILTERS = { istable: 0, issingle: 0 };

const columns: GridColumn[] = [
	{ fieldname: "append_to", label: "Append To", reqd: true },
	{ fieldname: "trigger_on", label: "Trigger On", reqd: true, width: 120 },
	{ fieldname: "message_field", label: "Message Text" },
	{ fieldname: "sender_field", label: "Phone Number", reqd: true },
	{ fieldname: "sender_name_field", label: "Contact Name", reqd: true },
	{ fieldname: "timestamp_field", label: "Message Time" },
];

const triggerOptions = ["Incoming", "Outgoing", "Both"];

function isMappingSlot(fieldname: string): fieldname is MappingSlot {
	return fieldname !== "append_to" && fieldname !== "trigger_on";
}

function onAppendTo(row: AppendAction, doctype: string | number | null) {
	props.controller.setAppendTo(row, doctype == null ? null : String(doctype));
}
</script>

<template>
	<Grid
		v-model="controller.doc.append_actions"
		:columns="columns"
		:new-row="emptyAppendAction"
		class="append-actions"
	>
		<template #cell="{ row, column, value, update }">
			<Link
				v-if="column.fieldname === 'append_to'"
				doctype="DocType"
				:filters="APPEND_TO_FILTERS"
				:model-value="value || null"
				placeholder=""
				@update:model-value="(v) => onAppendTo(row as AppendAction, v)"
			/>
			<Select
				v-else-if="column.fieldname === 'trigger_on'"
				:model-value="value"
				:options="triggerOptions"
				@update:model-value="update"
			/>
			<Combobox
				v-else-if="isMappingSlot(column.fieldname)"
				:model-value="value || null"
				:options="controller.optionsFor(row.append_to, column.fieldname)"
				:disabled="!row.append_to"
				placeholder=""
				@update:model-value="(v) => update(v ?? '')"
			/>
		</template>
	</Grid>
</template>

<style scoped>
/* Grid always draws a per-row edit button for a row dialog; every field here edits inline. */
.append-actions :deep(.grid-row > div:last-child button) {
	display: none;
}
</style>
