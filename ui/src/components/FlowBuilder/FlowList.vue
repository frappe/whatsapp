<script setup lang="ts">
import { computed, ref } from "vue";
import { Badge, Button, Skeleton, TextInput, dayjsLocal, toast } from "frappe-ui";
import ConfirmDeleteButton from "../common/ConfirmDeleteButton.vue";
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
import FlowListFilter from "./FlowListFilter.vue";
import { STATUS_THEME } from "./status";
import type { WhatsAppFlowStatus } from "../Messages/types";
import type { FlowCategory, FlowListProps, FlowListRow } from "./types";
import { serverErrorMessage } from "../../utils/serverError";

const props = defineProps<FlowListProps>();
const emit = defineEmits<{ open: [name: string]; new: [] }>();

const chrome = useChrome(() => props.chrome);
const COLUMNS = ["minmax(0,2fr)", "7rem", "minmax(0,1fr)", "8rem", "8rem"];
const columns = computed(() => (props.canWrite ? [...COLUMNS, "2.5rem"] : COLUMNS));
const SKELETON_ROWS = 4;

const direction = ref<"asc" | "desc">("desc");
const search = ref("");
const statusFilter = ref<WhatsAppFlowStatus[]>([]);
const categoryFilter = ref<FlowCategory[]>([]);
const filtering = computed(() => Boolean(search.value.trim() || statusFilter.value.length || categoryFilter.value.length));

const rows = computed(() => {
	const sorted = props.controller.rows.filter(matches).sort((a, b) => a.modified.localeCompare(b.modified));
	return direction.value === "asc" ? sorted : sorted.reverse();
});

function matches(row: FlowListRow) {
	const query = search.value.trim().toLowerCase();
	if (query && !row.flow_name.toLowerCase().includes(query)) return false;
	if (statusFilter.value.length && !statusFilter.value.includes(row.status)) return false;
	return !categoryFilter.value.length || categoryFilter.value.some((c) => row.categories.includes(c));
}

function clearFilters() {
	search.value = "";
	statusFilter.value = [];
	categoryFilter.value = [];
}
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

/** A refusal, such as templates still using the Flow, shows as a toast. */
async function deleteFlow(row: FlowListRow) {
	try {
		await props.controller.remove(row.name);
	} catch (e) {
		toast.error(serverErrorMessage(e));
	}
}
</script>

<template>
	<div class="flex flex-col gap-6 text-ink-gray-8">
		<div v-if="!hideHeader" class="flex items-start justify-between gap-4">
			<div class="flex min-w-0 flex-col gap-1">
				<h2 class="text-xl-semibold text-ink-gray-9">{{ chrome.listTitle }}</h2>
				<p class="text-p-base text-ink-gray-6">{{ chrome.listDescription }}</p>
			</div>
			<div v-if="canWrite" class="flex shrink-0 items-center gap-2">
				<Button
					variant="solid"
					icon-left="lucide-plus"
					:label="chrome.newFlow"
					@click="emit('new')"
				/>
			</div>
		</div>

		<div v-if="!controller.error" class="flex items-center gap-2">
			<template v-if="controller.rows.length">
				<TextInput
					v-model="search"
					class="min-w-0 flex-1"
					:placeholder="chrome.searchFlows"
					:debounce="200"
				>
					<template #prefix>
						<span class="lucide-search size-4 text-ink-gray-6" aria-hidden="true" />
					</template>
				</TextInput>
				<FlowListFilter v-model:statuses="statusFilter" v-model:categories="categoryFilter" :chrome="chrome" />
			</template>
			<!-- Meta owns a Flow's status, so it moves only on a sync or a webhook. -->
			<Button
				v-if="canWrite && controller.account"
				class="ml-auto shrink-0"
				icon-left="lucide-refresh-cw"
				:label="chrome.syncFlows"
				:loading="controller.syncing"
				@click="controller.sync()"
			/>
		</div>

		<div v-if="controller.error" class="flex flex-col items-center gap-3 py-16 text-center">
			<p class="text-p-base text-ink-gray-7">
				{{ chrome.listError }}: {{ serverErrorMessage(controller.error) }}
			</p>
			<Button :label="chrome.retry" @click="controller.load()" />
		</div>

		<div
			v-else-if="controller.loaded && !rows.length && filtering"
			class="flex flex-col items-center gap-3 py-16 text-center"
		>
			<p class="text-base-medium text-ink-gray-8">{{ chrome.noMatches }}</p>
			<Button :label="chrome.clearFilters" @click="clearFilters" />
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
				v-if="canWrite"
				variant="solid"
				icon-left="lucide-plus"
				:label="chrome.newFlow"
				@click="emit('new')"
			/>
		</div>

		<!-- In dark mode the list's own divider colour matches a dialog's elevated surface. -->
		<List
			v-else
			:columns="columns"
			:row-height="44"
			class="list-row-px-3 [&_[data-slot=list-divider]]:border-outline-elevation-2 [&_[data-slot=list-header-border]]:border-outline-elevation-2"
		>
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
				<ListHeaderCell v-if="canWrite" />
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
						<ListCell v-if="canWrite" />
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
						<ListCell v-if="canWrite">
							<ConfirmDeleteButton
								v-if="item.status === 'Draft'"
								:label="chrome.deleteFlow"
								:confirm-label="chrome.confirmDelete"
								@confirm="deleteFlow(item as FlowListRow)"
							/>
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
