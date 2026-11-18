<script setup lang="ts">
import { computed, ref } from "vue";
import { Badge, Button, Skeleton, dayjsLocal } from "frappe-ui";
import {
	List,
	ListCell,
	ListHeader,
	ListHeaderCell,
	ListHeaderCellSort,
	ListRow,
	ListRows,
} from "frappe-ui/list";
import { format } from "./chrome";
import { useChrome } from "./context";
import { STATUS_THEME } from "./status";
import type { FlowListProps, FlowListRow } from "./types";
import { serverErrorMessage } from "../../utils/serverError";

const props = defineProps<FlowListProps>();
const emit = defineEmits<{ open: [name: string]; new: [] }>();

const chrome = useChrome(() => props.chrome);
const COLUMNS = ["minmax(0,1fr)", "7rem", "minmax(0,14rem)", "8rem", "8rem"];
const SKELETON_ROWS = 4;

const direction = ref<"asc" | "desc">("desc");
const rows = computed(() => {
	const sorted = [...props.controller.rows].sort((a, b) => a.modified.localeCompare(b.modified));
	return direction.value === "asc" ? sorted : sorted.reverse();
});
const firstLoad = computed(() => !props.controller.loaded && !props.controller.error);

function usedBy(row: FlowListRow) {
	if (!row.used_by) return chrome.value.usedByNone;
	return row.used_by === 1
		? chrome.value.usedByOne
		: format(chrome.value.usedByMany, row.used_by);
}

function categories(row: FlowListRow) {
	return row.categories.map((category) => chrome.value[category] ?? category).join(", ");
}
</script>

<template>
	<div class="flex flex-col gap-6 text-ink-gray-8">
		<div class="flex items-start justify-between gap-4">
			<div class="flex min-w-0 flex-col gap-1">
				<h2 class="text-xl-semibold text-ink-gray-9">{{ chrome.listTitle }}</h2>
				<p class="text-p-base text-ink-gray-6">{{ chrome.listDescription }}</p>
			</div>
			<div class="flex shrink-0 items-center gap-2">
				<Button
					v-if="controller.account"
					variant="subtle"
					icon-left="lucide-refresh-cw"
					:label="chrome.syncFlows"
					:loading="controller.syncing"
					@click="controller.sync()"
				/>
				<Button
					variant="solid"
					icon-left="lucide-plus"
					:label="chrome.newFlow"
					@click="emit('new')"
				/>
			</div>
		</div>

		<div v-if="controller.error" class="flex flex-col items-center gap-3 py-16 text-center">
			<p class="text-p-base text-ink-gray-7">
				{{ chrome.listError }}: {{ serverErrorMessage(controller.error) }}
			</p>
			<Button :label="chrome.retry" @click="controller.load()" />
		</div>

		<div
			v-else-if="controller.loaded && !rows.length"
			class="flex flex-col items-center gap-3 py-16 text-center"
		>
			<div class="flex size-12 items-center justify-center rounded-full bg-surface-gray-2">
				<span class="lucide-clipboard-list size-6 text-ink-gray-6" aria-hidden="true" />
			</div>
			<div class="flex flex-col gap-1">
				<p class="text-base-medium text-ink-gray-8">{{ chrome.emptyTitle }}</p>
				<p class="text-p-sm text-ink-gray-6">{{ chrome.emptyDescription }}</p>
			</div>
			<Button
				variant="solid"
				icon-left="lucide-plus"
				:label="chrome.newFlow"
				@click="emit('new')"
			/>
		</div>

		<List v-else :columns="COLUMNS" :row-height="44" class="list-row-px-3">
			<ListHeader>
				<ListHeaderCell>{{ chrome.columnName }}</ListHeaderCell>
				<ListHeaderCell>{{ chrome.columnStatus }}</ListHeaderCell>
				<ListHeaderCell>{{ chrome.columnCategories }}</ListHeaderCell>
				<ListHeaderCell>{{ chrome.columnUsedBy }}</ListHeaderCell>
				<ListHeaderCellSort
					:direction="direction"
					@click="direction = direction === 'desc' ? 'asc' : 'desc'"
				>
					{{ chrome.columnUpdated }}
				</ListHeaderCellSort>
			</ListHeader>
			<ListRows
				v-if="firstLoad"
				:items="Array.from({ length: SKELETON_ROWS }, (_, i) => ({ name: i }))"
			>
				<template #default="{ value }">
					<ListRow :value="value">
						<ListCell><Skeleton class="h-4 w-48 rounded-4" /></ListCell>
						<ListCell><Skeleton class="h-5 w-16 rounded-4" /></ListCell>
						<ListCell><Skeleton class="h-4 w-28 rounded-4" /></ListCell>
						<ListCell><Skeleton class="h-4 w-20 rounded-4" /></ListCell>
						<ListCell><Skeleton class="h-4 w-16 rounded-4" /></ListCell>
					</ListRow>
				</template>
			</ListRows>
			<ListRows v-else :items="rows">
				<template #default="{ item, value }">
					<ListRow :value="value" @click="emit('open', (item as FlowListRow).name)">
						<ListCell>
							<span class="truncate text-base-medium text-ink-gray-8">{{
								item.flow_name
							}}</span>
						</ListCell>
						<ListCell>
							<Badge
								variant="subtle"
								:theme="STATUS_THEME[(item as FlowListRow).status]"
								:label="chrome[(item as FlowListRow).status]"
							/>
						</ListCell>
						<ListCell>
							<span class="truncate text-base text-ink-gray-7">{{
								categories(item as FlowListRow)
							}}</span>
						</ListCell>
						<ListCell>
							<span
								class="text-base"
								:class="item.used_by ? 'text-ink-gray-7' : 'text-ink-gray-5'"
							>
								{{ usedBy(item as FlowListRow) }}
							</span>
						</ListCell>
						<ListCell>
							<span class="text-base text-ink-gray-5">{{
								dayjsLocal(item.modified).fromNow()
							}}</span>
						</ListCell>
					</ListRow>
				</template>
			</ListRows>
		</List>
		<p v-if="controller.syncedAt" class="text-sm text-ink-gray-5">
			{{ format(chrome.syncedAt, dayjsLocal(controller.syncedAt).fromNow()) }}
		</p>
	</div>
</template>
