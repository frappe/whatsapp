<script setup lang="ts">
import { markRaw, reactive, shallowRef, watch } from "vue";
import { Button, Dialog, LoadingIndicator } from "frappe-ui";
import { frappeFlowApi } from "../api";
import type { FlowBuilderChrome } from "../chrome";
import { provideBuilder, useChrome, type BuilderContext } from "../context";
import { createFlow, parse, type FlowModel } from "../model";
import type { PreviewSettings } from "../types";
import { PreviewRun } from "./interactive";
import PhoneFrame from "./PhoneFrame.vue";
import { serverErrorMessage } from "../../../utils/serverError";

/** A Flow's phone preview outside the builder, interactive from its first screen. */
const props = defineProps<{ flow: string; title?: string; chrome?: Partial<FlowBuilderChrome> }>();
const open = defineModel<boolean>("open", { required: true });

const chrome = useChrome(() => props.chrome);
// The phone's parts read only `chrome` from the builder's context.
provideBuilder({ chrome } as unknown as BuilderContext);

const settings = reactive<PreviewSettings>({ interactive: true, theme: "light" });
const model = shallowRef<FlowModel | null>(null);
const run = shallowRef<PreviewRun | null>(null);
const error = shallowRef<unknown>(null);

watch(
	() => open.value && props.flow,
	async (flow) => {
		if (!flow) return;
		model.value = null;
		error.value = null;
		try {
			const { flow_json } = await frappeFlowApi.get(flow);
			const json = typeof flow_json === "string" ? JSON.parse(flow_json) : flow_json;
			const parsed = markRaw(json ? parse(json) : createFlow());
			const next = reactive(new PreviewRun(parsed)) as PreviewRun;
			next.start();
			model.value = parsed;
			run.value = next;
		} catch (e) {
			error.value = e;
		}
	},
	{ immediate: true }
);
</script>

<template>
	<Dialog v-model:open="open" size="md">
		<template #title>
			<div class="flex items-center gap-2">
				<h3 class="flex-1 truncate text-2xl-semibold leading-6 text-ink-gray-8">
					{{ title || chrome.preview }}
				</h3>
				<Button
					v-if="run"
					variant="ghost"
					icon="lucide-rotate-ccw"
					:aria-label="chrome.restartPreview"
					:title="chrome.restartPreview"
					@click="run.restart()"
				/>
			</div>
		</template>
		<div class="flex flex-col items-center">
			<p v-if="error" class="py-16 text-center text-p-base text-ink-gray-7">
				{{ serverErrorMessage(error) }}
			</p>
			<div v-else-if="!model || !run" class="flex h-96 items-center justify-center">
				<LoadingIndicator class="size-5" />
			</div>
			<PhoneFrame v-else :model="model" :run="run" :settings="settings" :highlight="null" />
		</div>
	</Dialog>
</template>
