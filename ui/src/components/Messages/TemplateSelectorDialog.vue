<!-- eslint-disable vue/no-v-html -->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { Button, Dialog, Spinner, TextInput } from "frappe-ui";
import TemplateButtons from "./TemplateButtons.vue";
import { formatWhatsAppMessage } from "./formatMessage";
import type { TemplateSelectorDialogProps } from "./types";

const props = withDefaults(defineProps<TemplateSelectorDialogProps>(), {
	templates: () => [],
	title: "WhatsApp Templates",
	searchPlaceholder: "Welcome Message",
	createLabel: "Create New Template",
	emptyLabel: "No Templates Found",
	emptyCreateLabel: "Create New",
});

const emit = defineEmits<{
	select: [templateName: string];
	"update:open": [value: boolean];
}>();

const search = ref("");
const searchInput = ref<{ el?: HTMLInputElement } | null>(null);

const show = computed({
	get: () => props.open,
	set: (value: boolean) => emit("update:open", value),
});

const filteredTemplates = computed(() =>
	props.templates.filter((template) =>
		template.name.toLowerCase().includes(search.value.toLowerCase())
	)
);

function select(templateName: string) {
	emit("select", templateName);
	show.value = false;
}

function createTemplate() {
	show.value = false;
	// `/app/whatsapp-template` is this app's own desk form, so it is always there.
	window.open("/app/whatsapp-template/new");
}

watch(
	() => props.open,
	(value) => {
		if (value) {
			search.value = "";
			nextTick(() => searchInput.value?.el?.focus());
		}
	}
);
</script>

<template>
	<Dialog v-model="show" :options="{ title, size: '4xl' }">
		<div class="flex w-full items-center gap-2">
			<TextInput
				ref="searchInput"
				v-model="search"
				class="w-full"
				type="text"
				:placeholder="searchPlaceholder"
			>
				<template #prefix>
					<span class="lucide-search h-4 w-4 text-ink-gray-4" aria-hidden="true" />
				</template>
			</TextInput>
			<Button :label="createLabel" variant="solid" @click="createTemplate">
				<template #prefix>
					<span class="lucide-plus h-4 w-4" aria-hidden="true" />
				</template>
			</Button>
		</div>

		<div v-if="loading && !templates.length" class="flex h-56 items-center justify-center">
			<Spinner class="size-5 text-ink-gray-5" />
		</div>
		<div
			v-else-if="filteredTemplates.length"
			class="mt-2 grid max-h-[560px] grid-cols-1 gap-2 overflow-y-auto sm:grid-cols-3"
		>
			<div
				v-for="template in filteredTemplates"
				:key="template.name"
				class="flex h-56 cursor-pointer flex-col gap-2 rounded-lg border p-3 hover:bg-surface-gray-2"
				@click="select(template.name)"
			>
				<div class="truncate border-b pb-2 text-base-semibold" :title="template.name">
					{{ template.name }}
				</div>
				<!--
					Previews what a send actually renders, mirroring MessageBubble's
					template branch — same formatter, same hierarchy. `buttons` is a child
					table the host has to fetch separately; without it the row simply
					shows header/body/footer.
				-->
				<div class="flex flex-1 flex-col gap-2 overflow-hidden text-sm text-ink-gray-5">
					<div v-if="template.header_text" class="text-base font-semibold">
						{{ template.header_text }}
					</div>
					<!--
						Only the body scrolls. The card is a fixed height, and footer and
						buttons are the parts a picker most needs to show, so they stay
						pinned and a long body gives up its space instead of clipping them.
						`min-h-0` is what lets this flex child shrink below its content.
					-->
					<div
						class="min-h-0 flex-1 overflow-y-auto"
						v-html="formatWhatsAppMessage(template.message)"
					/>
					<div v-if="template.footer" class="text-xs text-ink-gray-5">
						{{ template.footer }}
					</div>
					<TemplateButtons :buttons="template.buttons" />
				</div>
			</div>
		</div>
		<div v-else class="mt-2">
			<div class="flex h-56 flex-col items-center justify-center">
				<div class="text-lg text-ink-gray-4">{{ emptyLabel }}</div>
				<Button :label="emptyCreateLabel" class="mt-4" @click="createTemplate" />
			</div>
		</div>
	</Dialog>
</template>
