<script setup lang="ts">
import { onMounted, ref, shallowRef, watch } from "vue";
import { CodeEditor, CodeEditorContent, CodeKit, loadLanguage } from "frappe-ui/code-editor";
import type { Extension } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import { format } from "../chrome";
import { useBuilder } from "../context";
import type { JsonError } from "../jsonText";

const props = defineProps<{ path?: string }>();
const { session, chrome } = useBuilder();

const printed = session.printed!;
const text = ref(printed.text);
const error = ref<JsonError | null>(null);
const editor = ref<{ editor: EditorView | null }>();

const kit = CodeKit.configure({ lineNumbers: {}, autocompletion: false });
const extensions = shallowRef<Extension[]>([kit]);
// JSON highlighting is an optional peer of frappe-ui; without it the text is plain.
loadLanguage("json")
	.then((json) => json && (extensions.value = [kit, json]))
	.catch(() => {});

watch(text, () => (error.value = null));

onMounted(() => {
	const line = props.path ? printed.lines.get(props.path) : undefined;
	if (line) requestAnimationFrame(() => goToLine(line));
});

function goToLine(line: number) {
	const view = editor.value?.editor;
	if (!view) return;
	const at = view.state.doc.line(Math.min(line, view.state.doc.lines));
	view.dispatch({ selection: { anchor: at.from }, scrollIntoView: true });
	view.focus();
}

/** False when the text is not valid JSON; the builder then stays on this tab. */
function apply(): boolean {
	if (session.readOnly) return true;
	error.value = session.applyJson(text.value);
	if (error.value) goToLine(error.value.line);
	return !error.value;
}

defineExpose({ apply });
</script>

<template>
	<div class="flex min-h-0 min-w-0 flex-1 flex-col">
		<div
			class="flex h-9 shrink-0 items-center gap-2 border-b border-outline-gray-1 px-3 text-sm"
		>
			<span
				v-if="error"
				class="flex min-w-0 items-center gap-1.5 text-ink-red-7"
				role="alert"
			>
				<span class="lucide-circle-alert size-4 shrink-0" aria-hidden="true" />
				<span class="truncate">{{
					format(chrome.jsonError, error.line, error.message)
				}}</span>
			</span>
			<span v-else class="truncate text-ink-gray-5">{{ chrome.jsonHint }}</span>
		</div>
		<CodeEditor
			ref="editor"
			v-model="text"
			:extensions="extensions"
			:editable="!session.readOnly"
		>
			<CodeEditorContent class="fb-json min-h-0 flex-1 overflow-auto" />
		</CodeEditor>
	</div>
</template>

<style>
.fb-json {
	--code-radius: 0;
	--code-border: transparent;
	--code-max-height: none;
	--code-min-height: 100%;
}
</style>
