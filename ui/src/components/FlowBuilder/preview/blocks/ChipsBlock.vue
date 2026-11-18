<script setup lang="ts">
import { computed } from "vue";
import { optionsOf, type Block, type JsonObject } from "../../model";
import { usePhoneBlock } from "../phone";

/** Chips (ChipsSelector): pick several from pills. */
const props = defineProps<{ block: Block }>();
const { phone, component, name, answer } = usePhoneBlock(props);

const options = computed(() => optionsOf(component.value));
const chosen = computed(() => (Array.isArray(answer.value) ? answer.value : []));

function toggle(option: JsonObject) {
	if (option.enabled === false) return;
	const id = String(option.id);
	const next = chosen.value.includes(id)
		? chosen.value.filter((each) => each !== id)
		: [...chosen.value, id];
	phone.run.set(name.value, next);
}
</script>

<template>
	<div class="flex flex-col gap-2">
		<p class="text-[13px] font-medium text-[var(--wa-ink)]">
			{{ phone.text(component.label) }}
		</p>
		<p v-if="component.description" class="-mt-1 text-[11px] text-[var(--wa-ink-2)]">
			{{ phone.text(component.description) }}
		</p>
		<div class="flex flex-wrap gap-2">
			<button
				v-for="option in options"
				:key="String(option.id)"
				type="button"
				class="flex h-8 items-center gap-1 rounded-full border px-3 text-[12px] transition-colors duration-150"
				:class="[
					chosen.includes(String(option.id))
						? 'border-[var(--wa-accent)] bg-[var(--wa-accent-soft)] text-[var(--wa-ink)]'
						: 'border-[var(--wa-field)] text-[var(--wa-ink)]',
					option.enabled === false && 'opacity-50',
				]"
				:aria-pressed="chosen.includes(String(option.id))"
				@click="toggle(option)"
			>
				<span
					v-if="chosen.includes(String(option.id))"
					class="lucide-check size-3"
					aria-hidden="true"
				/>
				{{ phone.text(option.title) }}
			</button>
		</div>
	</div>
</template>
