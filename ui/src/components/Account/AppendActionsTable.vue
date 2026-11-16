<script setup lang="ts">
import { computed } from "vue";
import { Combobox, Select } from "frappe-ui";
import { Grid, type GridColumn } from "@framework/ui/components/Grid";
import { Link } from "@framework/ui/components/Link";
import { emptyAppendAction } from "./useAccount";
import type { AppendAction, AppendActionsTableProps, MappingSlot } from "./types";

const props = defineProps<AppendActionsTableProps>();

const isManaged = (row: AppendAction) => props.controller.managedDoctypes.includes(row.append_to);

// A host's managed rows are its settings' to switch, so the table edits the others and puts
// the managed ones back on every change. Rows are shared objects, so inline edits need no merge.
const rows = computed({
	get: () => props.controller.doc.append_actions.filter((row) => !isManaged(row)),
	set: (shown: AppendAction[]) => {
		const managed = props.controller.doc.append_actions.filter(isManaged);
		props.controller.doc.append_actions = [...managed, ...shown];
	},
});

// Only documents a message can be appended to: child rows and singles have no list to add to,
// and a host's managed doctype is switched from its settings instead.
const appendToFilters = computed(() => {
	const managed = props.controller.managedDoctypes;
	const base = { istable: 0, issingle: 0 };
	return managed.length ? { ...base, name: ["not in", managed] } : base;
});

const columns: GridColumn[] = [
	{ fieldname: "append_to", label: "Append To", reqd: true },
	{ fieldname: "trigger_on", label: "Trigger On", reqd: true, width: 120 },
	{ fieldname: "message_field", label: "Message Text" },
	{ fieldname: "sender_field", label: "Phone Number" },
	{ fieldname: "sender_name_field", label: "Contact Name" },
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
	<Grid v-model="rows" :columns="columns" :new-row="emptyAppendAction" class="append-actions">
		<template #cell="{ row, column, value, update }">
			<Link
				v-if="column.fieldname === 'append_to'"
				doctype="DocType"
				:filters="appendToFilters"
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
