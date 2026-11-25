<script setup lang="ts">
import { computed } from "vue";
import { Button, toast } from "frappe-ui";
import {
	canRestore,
	deleteScreenInJourney,
	journeyScreens,
	moveScreenInJourney,
	readMoreParent,
	restoreScreens,
	type RemovedScreens,
	type Screen,
} from "../model";
import { format } from "../chrome";
import { useBuilder } from "../context";
import AddScreen from "./AddScreen.vue";
import { screenTitle } from "./describe";
import { screenSeverity } from "./problems";
import { titleRow } from "./rows";
import { useSortable } from "./sortable";

/** Meta's screens list. The order is the journey; "Read more" screens sit under their Opt-in's screen. */
const { session, chrome, edit, rows } = useBuilder();

const model = computed(() => session.model!);
/** Interactive mode walks the screens as they are, so they can't be added, moved or deleted meanwhile. */
const fixed = computed(() => session.readOnly || session.preview.interactive);
const journey = computed(() => journeyScreens(model.value));
const byUid = computed(() => new Map(model.value.screens.map((screen) => [screen.uid, screen])));
const subScreens = computed(() => {
	const found = new Map<string, Screen[]>();
	for (const screen of model.value.screens) {
		const parent = readMoreParent(model.value, screen.uid)?.screen;
		if (parent) found.set(parent.uid, [...(found.get(parent.uid) ?? []), screen]);
	}
	return found;
});

const sortable = useSortable({
	ids: () => journey.value.map((screen) => screen.uid),
	move: (uid, index) => edit((current) => moveScreenInJourney(current, uid, index)),
	disabled: () => fixed.value,
});

function select(screen: Screen) {
	if (session.selection.screen !== screen.uid) session.select(screen.uid, null);
}

/** No confirm, as in Meta; the toast can put the screen back. */
function remove(screen: Screen) {
	const title = screenTitle(screen, model.value, chrome.value);
	const { model: without, removed } = deleteScreenInJourney(model.value, screen.uid);
	edit(() => without);
	const generation = session.generation;
	toast(format(chrome.value.screenDeleted, title), {
		action: { label: chrome.value.undo, onClick: () => undo(removed, generation) },
	});
}

/** A reload or Edit JSON since the delete renumbers the model, so the old screens can't go back. */
function undo(removed: RemovedScreens, generation: number) {
	if (generation !== session.generation || !canRestore(model.value, removed)) {
		toast.error(chrome.value.cantUndoDelete);
		return;
	}
	edit((current) => restoreScreens(current, removed));
}

function added(uid: string) {
	rows.openRow(byUid.value.get(uid)!, titleRow(uid));
}
</script>

<template>
	<section class="flex min-h-0 flex-col gap-1" :aria-label="chrome.screens">
		<div class="flex items-center gap-2 px-1 pb-1">
			<h2 class="flex-1 text-base-medium text-ink-gray-8">{{ chrome.screens }}</h2>
			<slot name="actions" />
		</div>
		<TransitionGroup
			tag="ul"
			name="fb-move"
			class="flex min-h-0 flex-col gap-0.5 overflow-y-auto"
		>
			<li
				v-for="uid in sortable.order.value"
				:key="uid"
				class="flex flex-col gap-0.5 transition-opacity duration-150"
				:class="sortable.dragging.value === uid && 'opacity-50'"
				v-bind="sortable.row(uid)"
			>
				<template
					v-for="(screen, depth) in [byUid.get(uid)!, ...(subScreens.get(uid) ?? [])]"
					:key="screen.uid"
				>
					<div
						class="group flex h-9 shrink-0 cursor-pointer items-center gap-1 rounded-4 pe-1 text-base transition-colors duration-100"
						:class="[
							session.selection.screen === screen.uid
								? 'bg-surface-gray-3 text-ink-gray-9'
								: 'text-ink-gray-7 hover:bg-surface-gray-2',
							depth ? 'ms-4' : '',
							session.readOnly ? 'ps-2' : 'ps-1',
						]"
						:aria-current="
							session.selection.screen === screen.uid ? 'true' : undefined
						"
						@click="select(screen)"
					>
						<span v-if="!session.readOnly" class="flex w-6 shrink-0 justify-center">
							<Button
								v-if="!depth && !fixed"
								variant="ghost"
								size="xs"
								icon="lucide-grip-vertical"
								class="cursor-grab text-ink-gray-5 active:cursor-grabbing"
								:aria-label="chrome.dragToReorder"
								v-bind="sortable.handle(uid)"
								@click.stop
							/>
							<span
								v-else-if="depth || session.preview.interactive"
								class="lucide-grip-vertical size-4 text-ink-gray-3"
								aria-hidden="true"
							/>
						</span>
						<button
							type="button"
							class="min-w-0 flex-1 truncate text-left"
							@click.stop="select(screen)"
						>
							{{ screenTitle(screen, model, chrome) }}
						</button>
						<span class="flex w-6 shrink-0 justify-center">
							<span
								v-if="screenSeverity(session.problems, screen.uid)"
								class="lucide-triangle-alert size-4"
								:class="
									screenSeverity(session.problems, screen.uid) === 'error'
										? 'text-ink-red-5'
										: 'text-ink-amber-5'
								"
								role="img"
								:aria-label="chrome.hasProblem"
							/>
						</span>
						<span class="flex w-7 shrink-0 justify-center">
							<Button
								v-if="!depth && !fixed && journey.length > 1"
								variant="ghost"
								size="sm"
								icon="lucide-x"
								:aria-label="chrome.deleteScreen"
								@click.stop="remove(screen)"
							/>
						</span>
					</div>
				</template>
			</li>
		</TransitionGroup>
		<AddScreen
			v-if="!session.readOnly"
			:class="session.preview.interactive && 'invisible'"
			@added="added"
		/>
	</section>
</template>
