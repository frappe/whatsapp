<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useElementSize, useEventListener } from "@vueuse/core";
import { Alert, Button, dialog } from "frappe-ui";
import BuilderHeader from "./builder/BuilderHeader.vue";
import BuilderSkeleton from "./builder/BuilderSkeleton.vue";
import ContentList from "./builder/ContentList.vue";
import PreviewColumn from "./builder/PreviewColumn.vue";
import ScreensList from "./builder/ScreensList.vue";
import JsonDialog from "./preview/JsonDialog.vue";
import PreviewToolbar from "./preview/PreviewToolbar.vue";
import { ContentRows, titleRow } from "./builder/rows";
import { format } from "./chrome";
import { provideBuilder, useChrome } from "./context";
import type { FlowModel } from "./model";
import type { FlowBuilderProps } from "./types";
import { whatsappManagerFlowsUrl } from "./status";
import { serverErrorMessage } from "../../utils/serverError";

const props = defineProps<FlowBuilderProps>();
const emit = defineEmits<{ close: []; copied: [name: string] }>();

const session = props.controller;
const chrome = useChrome(() => props.chrome);
const rows = new ContentRows(session);

provideBuilder({
	session,
	chrome,
	rows,
	edit(change: (model: FlowModel) => FlowModel) {
		if (session.model && !session.readOnly) session.apply(change(session.model));
	},
});

/** Below this width the preview leaves the columns and opens over them. */
const NARROW_PX = 720;
const root = ref<HTMLElement>();
const { width } = useElementSize(root, { width: NARROW_PX, height: 0 });
const narrow = computed(() => width.value < NARROW_PX);
const previewOpen = ref(false);
const editingJson = ref(false);
const publishing = ref(false);

const screen = computed(
	() => session.model?.screens.find((each) => each.uid === session.selection.screen) ?? null
);

/** As in Meta, the first screen opens with its title row open. */
watch(
	() => !!session.model,
	(loaded) => {
		const first = session.model?.screens[0];
		if (loaded && first) rows.openRow(first, titleRow(first.uid));
	},
	{ immediate: true }
);

const readOnlyAlert = computed(() => {
	const status = session.flow?.status;
	if (!session.readOnly || !status) return null;
	const titles: Record<string, string> = {
		Published: chrome.value.readOnlyPublished,
		Deprecated: chrome.value.readOnlyDeprecated,
		Throttled: chrome.value.readOnlyThrottled,
		Blocked: chrome.value.readOnlyBlocked,
	};
	const themes: Record<string, "red" | "amber"> = { Blocked: "red", Throttled: "amber" };
	const managerUrl =
		themes[status] && session.flow?.business_id
			? whatsappManagerFlowsUrl(session.flow.business_id)
			: null;
	return { title: titles[status], theme: themes[status] ?? "gray", managerUrl };
});

let closing = false;

/** Closing saves first; it asks only when the last changes couldn't be saved. */
async function close() {
	if (closing) return;
	closing = true;
	const saved = await session.flush();
	closing = false;
	if (saved) return emit("close");
	dialog.confirm({
		title: chrome.value.closeTitle,
		message: chrome.value.closeMessage,
		theme: "red",
		confirmLabel: chrome.value.close,
		onConfirm: () => emit("close"),
	});
}

/** Escape closes the builder unless it belongs to a dialog or menu open above it. */
function closeOnEscape(event: KeyboardEvent) {
	if (event.key !== "Escape" || event.defaultPrevented || overlayAbove()) return;
	close();
}

function overlayAbove(): boolean {
	const overlays = document.querySelectorAll(
		'[role="dialog"], [role="alertdialog"], [role="menu"], [role="listbox"]'
	);
	return [...overlays].some((overlay) => !root.value || !overlay.contains(root.value));
}

useEventListener(window, "keydown", closeOnEscape);

async function publish() {
	publishing.value = true;
	const saved = await session.flush();
	publishing.value = false;
	if (!saved || session.errorCount) return;
	dialog.confirm({
		title: chrome.value.publishTitle,
		message: chrome.value.publishMessage,
		confirmLabel: chrome.value.publish,
		async onConfirm() {
			publishing.value = true;
			try {
				await rethrowReadable(() => session.publish());
			} finally {
				publishing.value = false;
			}
		},
	});
}

async function makeCopy() {
	await session.flush();
	dialog.prompt({
		title: chrome.value.copyTitle,
		fields: [
			{
				name: "flow_name",
				label: chrome.value.nameLabel,
				required: true,
				defaultValue: format(chrome.value.copyName, session.flow?.flow_name ?? ""),
			},
		],
		confirmLabel: chrome.value.makeCopy,
		async onConfirm({ values }) {
			const name = await rethrowReadable(() =>
				session.copy(String(values.flow_name).trim())
			);
			emit("copied", name);
		},
	});
}

/** The confirm dialog prints a thrown Error's message; a server error's text is on `messages`. */
async function rethrowReadable<T>(run: () => Promise<T>): Promise<T> {
	try {
		return await run();
	} catch (e) {
		throw new Error(serverErrorMessage(e));
	}
}
</script>

<template>
	<div ref="root" class="flex h-full min-h-0 flex-col bg-surface-base text-ink-gray-8">
		<BuilderSkeleton v-if="!session.model && !session.loadError" />
		<div
			v-else-if="!session.model"
			class="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center"
		>
			<p class="text-p-base text-ink-gray-7">
				{{ chrome.loadError }}: {{ serverErrorMessage(session.loadError) }}
			</p>
			<div class="flex gap-2">
				<Button :label="chrome.close" @click="emit('close')" />
				<Button variant="solid" :label="chrome.retry" @click="session.load()" />
			</div>
		</div>
		<template v-else>
			<BuilderHeader :publishing="publishing" @close="close" @publish="publish" />
			<div v-if="readOnlyAlert" class="border-b border-outline-gray-1 px-3 py-2">
				<Alert
					:theme="readOnlyAlert.theme"
					:primary-action="{ label: chrome.makeCopy, onClick: makeCopy }"
				>
					<template #title>
						{{ readOnlyAlert.title }}
						<a
							v-if="readOnlyAlert.managerUrl"
							:href="readOnlyAlert.managerUrl"
							target="_blank"
							rel="noopener noreferrer"
							class="inline-flex items-center gap-0.5 underline decoration-outline-gray-3 underline-offset-2 hover:decoration-ink-gray-7"
						>
							{{ chrome.seeWhyInManager }}
							<span class="lucide-arrow-up-right size-3.5" aria-hidden="true" />
						</a>
					</template>
				</Alert>
			</div>
			<div
				class="relative grid min-h-0 flex-1"
				:class="narrow ? 'grid-cols-1' : 'grid-cols-2 divide-x divide-outline-gray-1'"
			>
				<div class="flex min-h-0 flex-col">
					<div class="flex max-h-[45%] shrink-0 flex-col px-4 pb-3 pt-4">
						<ScreensList>
							<template v-if="narrow" #actions>
								<Button
									variant="outline"
									icon-left="lucide-smartphone"
									:label="chrome.preview"
									@click="previewOpen = true"
								/>
							</template>
						</ScreensList>
					</div>
					<div class="mx-5 shrink-0 border-t border-outline-gray-1" />
					<section class="flex min-h-0 flex-1 flex-col" :aria-label="chrome.editContent">
						<h2 class="shrink-0 px-5 pb-2 pt-4 text-base-medium text-ink-gray-8">
							{{ chrome.editContent }}
						</h2>
						<div
							class="min-h-0 flex-1 overflow-y-auto px-4 pb-10 [scrollbar-gutter:stable]"
						>
							<ContentList v-if="screen" :key="screen.uid" :screen="screen" />
						</div>
					</section>
				</div>
				<Transition name="fb-fade">
					<PreviewColumn
						v-show="!narrow || previewOpen"
						:class="narrow && 'absolute inset-0 z-10 shadow-lg'"
						:highlight="session.selection.block"
						@pick="(uid) => screen && rows.reveal(screen.uid, uid)"
					>
						<template #toolbar>
							<PreviewToolbar :compact="narrow" @edit-json="editingJson = true" />
							<Button
								v-if="narrow"
								variant="ghost"
								icon="lucide-x"
								:aria-label="chrome.closePreview"
								@click="previewOpen = false"
							/>
						</template>
					</PreviewColumn>
				</Transition>
				<Transition name="fb-fade">
					<div
						v-if="session.conflict"
						class="absolute inset-x-0 top-3 z-20 flex justify-center px-3"
					>
						<Alert
							class="w-full max-w-xl shadow-lg"
							theme="amber"
							:title="chrome.conflictTitle"
							:description="chrome.conflictMessage"
							:primary-action="{
								label: chrome.reload,
								onClick: () => session.load(),
							}"
						/>
					</div>
				</Transition>
			</div>
			<JsonDialog v-model:open="editingJson" />
		</template>
	</div>
</template>

<style>
.fb-fade-enter-active,
.fb-fade-leave-active {
	transition: opacity 150ms ease-out;
}
.fb-fade-enter-from,
.fb-fade-leave-to {
	opacity: 0;
}
.fb-move-move {
	transition: transform 200ms cubic-bezier(0.23, 1, 0.32, 1);
}
@media (prefers-reduced-motion: reduce) {
	.fb-move-move {
		transition: none;
	}
}
.fb-counted input[aria-invalid="true"],
.fb-counted textarea[aria-invalid="true"] {
	box-shadow: inset 0 0 0 1px var(--outline-red-3);
}
.fb-lifted {
	position: fixed;
	top: -1000px;
	left: 0;
	list-style: none;
	background: var(--surface-base);
	border-radius: 10px;
	box-shadow: var(--elevation-lg);
}
</style>
