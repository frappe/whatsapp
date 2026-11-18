<script setup lang="ts">
import { computed } from "vue";
import type { Block, JsonObject } from "../model";
import { usePhone } from "./phone";
import PhoneHeader from "./PhoneHeader.vue";

/** A Dropdown's options, full screen over the sheet as WhatsApp shows them. */
const props = defineProps<{ block: Block }>();
const emit = defineEmits<{ close: [] }>();
const phone = usePhone();

const name = computed(() => String(props.block.component.name ?? ""));
const options = computed(() => {
	const source = props.block.component["data-source"];
	return Array.isArray(source) ? (source as JsonObject[]) : [];
});

function choose(option: JsonObject) {
	if (option.enabled === false) return;
	phone.run.set(name.value, String(option.id));
	emit("close");
}
</script>

<template>
	<div class="absolute inset-0 z-10 flex flex-col bg-[var(--wa-sheet)]">
		<PhoneHeader :title="phone.text(block.component.label)" back @back="emit('close')" />
		<ul class="min-h-0 flex-1 overflow-y-auto py-2" role="listbox">
			<li v-for="option in options" :key="String(option.id)">
				<button
					type="button"
					role="option"
					:aria-selected="phone.run.value(name) === String(option.id)"
					class="flex min-h-10 w-full items-center gap-3 px-5 py-2 text-left"
					:class="option.enabled === false && 'opacity-50'"
					@click="choose(option)"
				>
					<span class="flex min-w-0 flex-1 flex-col">
						<span class="text-[13px] text-[var(--wa-ink)]">{{
							phone.text(option.title)
						}}</span>
						<span
							v-if="option.description"
							class="text-[11px] text-[var(--wa-ink-2)]"
							>{{ phone.text(option.description) }}</span
						>
					</span>
					<span
						v-if="phone.run.value(name) === String(option.id)"
						class="lucide-check size-4 shrink-0 text-[var(--wa-accent)]"
						aria-hidden="true"
					/>
				</button>
			</li>
		</ul>
	</div>
</template>
