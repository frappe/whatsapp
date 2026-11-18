<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import {
	TEXT_LIMITS,
	deleteBlock,
	followsListOrder,
	kindOf,
	moveBlock,
	readMoreParent,
	renameScreen,
	setFooter,
	type Block,
	type Screen,
} from "../model";
import { useBuilder } from "../context";
import AddContent from "./AddContent.vue";
import ContentRow from "./ContentRow.vue";
import CountedInput from "./CountedInput.vue";
import RowMessages from "./RowMessages.vue";
import { blockSummary, kindName, setInJson, text } from "./describe";
import BlockEditor from "./editors/BlockEditor.vue";
import { fieldError, rowSeverity } from "./problems";
import { titleRow } from "./rows";
import { useSortable } from "./sortable";

/** "Edit content": Screen title first, the components, the Button last. */
const props = defineProps<{ screen: Screen }>();
const { session, chrome, edit, rows } = useBuilder();

const list = ref<HTMLElement>();
onMounted(() => rows.attach(list.value ?? null));

const model = computed(() => session.model!);
const blocks = computed(() => new Map(props.screen.blocks.map((block) => [block.uid, block])));
const linear = computed(() => followsListOrder(model.value));
const readMore = computed(() => !!readMoreParent(model.value, props.screen.uid));
const footer = computed(() => props.screen.footer);

const sortable = useSortable({
	ids: () => props.screen.blocks.map((block) => block.uid),
	move: (uid, index) => edit((current) => moveBlock(current, uid, props.screen.uid, index)),
	disabled: () => session.readOnly,
});

function actions(block: Block, index: number) {
	if (session.readOnly) return [];
	const last = props.screen.blocks.length - 1;
	return [
		{
			label: chrome.value.moveUp,
			icon: "lucide-arrow-up",
			disabled: index === 0,
			onClick: () => sortable.step(block.uid, -1),
		},
		{
			label: chrome.value.moveDown,
			icon: "lucide-arrow-down",
			disabled: index === last,
			onClick: () => sortable.step(block.uid, 1),
		},
		{
			label: chrome.value.delete,
			icon: "lucide-trash-2",
			theme: "red" as const,
			onClick: () => edit((current) => deleteBlock(current, block.uid)),
		},
	];
}

/**
 * A new component arrives open, its main text selected, so typing replaces Meta's "Label". The
 * menu hands focus back to its trigger as it closes, so the field takes it back once.
 */
async function opened(uid: string) {
	rows.openRow(props.screen, uid);
	await nextTick();
	const row = list.value?.querySelector(`[data-row="${uid}"]`);
	row?.scrollIntoView({ block: "nearest", behavior: "smooth" });
	const field = row?.querySelector<HTMLElement>("[data-main-field]");
	const input = (
		field?.matches("input, textarea") ? field : field?.querySelector("textarea, input")
	) as HTMLInputElement | null | undefined;
	if (!input) return;
	const take = () => {
		input.focus();
		input.select();
	};
	take();
	const retake = (event: FocusEvent) => event.target !== input && take();
	document.addEventListener("focusin", retake, { once: true });
	setTimeout(() => document.removeEventListener("focusin", retake), 500);
}
</script>

<template>
	<div ref="list" class="flex flex-col gap-2">
		<ul class="flex flex-col gap-2">
			<ContentRow
				:id="titleRow(screen.uid)"
				:title="chrome.screenTitle"
				:summary="text(screen.props.title)"
				:open="rows.isOpen(titleRow(screen.uid))"
				:severity="rowSeverity(session.problems, screen.uid)"
				@toggle="rows.toggle(screen, titleRow(screen.uid))"
			>
				<CountedInput
					:aria-label="chrome.screenTitle"
					:model-value="text(screen.props.title)"
					:error="
						fieldError(session.problems, chrome, {
							screen: screen.uid,
							property: 'title',
						})
					"
					@update:model-value="
						(title) => edit((current) => renameScreen(current, screen.uid, title))
					"
				/>
				<RowMessages :screen="screen.uid" />
			</ContentRow>
		</ul>
		<TransitionGroup tag="ul" name="fb-move" class="flex flex-col gap-2">
			<ContentRow
				v-for="(uid, index) in sortable.order.value"
				:id="uid"
				:key="uid"
				v-bind="sortable.row(uid)"
				:title="kindName(blocks.get(uid)!, chrome)"
				:summary="blockSummary(blocks.get(uid)!, chrome)"
				:open="rows.isOpen(uid) && !!kindOf(blocks.get(uid)!)"
				:locked="!kindOf(blocks.get(uid)!)"
				:severity="rowSeverity(session.problems, screen.uid, uid)"
				:handle="session.readOnly ? undefined : sortable.handle(uid)"
				:actions="actions(blocks.get(uid)!, index)"
				:dragging="sortable.dragging.value === uid"
				@toggle="rows.toggle(screen, uid)"
			>
				<BlockEditor :block="blocks.get(uid)!" :screen="screen" />
			</ContentRow>
		</TransitionGroup>
		<ul v-if="footer" class="flex flex-col">
			<ContentRow
				:id="footer.uid"
				:title="chrome.Footer"
				:summary="text(footer.component.label)"
				:open="rows.isOpen(footer.uid)"
				:severity="rowSeverity(session.problems, screen.uid, footer.uid)"
				@toggle="rows.toggle(screen, footer.uid)"
			>
				<CountedInput
					:label="chrome.buttonLabel"
					:model-value="text(footer.component.label)"
					:limit="TEXT_LIMITS.Footer.label"
					:error="
						fieldError(session.problems, chrome, {
							screen: screen.uid,
							item: footer.uid,
							property: 'label',
						})
					"
					@update:model-value="
						(label) => edit((current) => setFooter(current, screen.uid, { label }))
					"
				/>
				<p v-if="!linear" class="flex items-center gap-1.5 text-p-sm text-ink-gray-6">
					<span class="lucide-corner-down-right size-3.5 shrink-0" aria-hidden="true" />
					{{ setInJson(screen, model, chrome) }}
				</p>
				<RowMessages :screen="screen.uid" :item="footer.uid" />
			</ContentRow>
		</ul>
		<p v-else-if="readMore" class="px-1 text-p-sm text-ink-gray-5">
			{{ chrome.readMoreHasNoButton }}
		</p>
		<AddContent v-if="!session.readOnly" class="pt-1" :screen="screen" @added="opened" />
	</div>
</template>
