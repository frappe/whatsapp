<script setup lang="ts">
import { useBuilder } from "../context";

/**
 * After the last screen: the chat with the Flow message and the contact's "Sent" reply, drawn as
 * Meta's playground draws it (gray bars for text), and Restart preview.
 */
const emit = defineEmits<{ restart: [] }>();
const { chrome } = useBuilder();
</script>

<template>
	<div class="absolute inset-0 flex flex-col bg-[var(--wa-wallpaper)]">
		<div class="flex h-12 shrink-0 items-center gap-2 bg-[var(--wa-sheet)] px-3">
			<span
				class="flex size-7 items-center justify-center rounded-full bg-[var(--wa-accent)] text-[var(--wa-accent-ink)]"
			>
				<span class="lucide-store size-4" aria-hidden="true" />
			</span>
			<span class="h-1.5 w-[90px] rounded-full bg-[var(--wa-accent)]" />
		</div>
		<div class="flex min-h-0 flex-1 flex-col gap-3 px-3 py-4" aria-hidden="true">
			<div class="self-end rounded-[8px] bg-[var(--wa-bubble-out)] px-3 py-2.5">
				<div class="h-1.5 w-24 rounded-full bg-[var(--wa-skeleton)]" />
			</div>
			<div class="flex w-[60%] flex-col rounded-[8px] bg-[var(--wa-bubble-in)]">
				<div class="flex flex-col gap-1.5 px-3 py-2.5">
					<div class="h-1.5 w-[85%] rounded-full bg-[var(--wa-skeleton)]" />
					<div class="h-1.5 w-[60%] rounded-full bg-[var(--wa-skeleton)]" />
				</div>
				<p
					class="border-t border-[var(--wa-divider)] py-1.5 text-center text-[10px] text-[var(--wa-ink-3)]"
				>
					{{ chrome.phoneOpenFlow }}
				</p>
			</div>
			<div
				class="flex w-[60%] flex-col gap-1 self-end rounded-[8px] bg-[var(--wa-bubble-out)] p-1"
			>
				<div
					class="flex flex-col gap-1.5 rounded-[6px] border-l-4 border-[var(--wa-accent)] bg-[var(--wa-accent-soft)] px-2 py-2"
				>
					<div class="h-1.5 w-[50%] rounded-full bg-[var(--wa-accent)]" />
					<div class="h-1.5 w-[80%] rounded-full bg-[var(--wa-skeleton)]" />
				</div>
				<p class="flex items-center gap-1 px-1 text-[10px] text-[var(--wa-ink-2)]">
					{{ chrome.phoneSent }}
					<span class="lucide-circle-check size-3" />
				</p>
			</div>
		</div>
		<div class="flex shrink-0 flex-col gap-2 p-2">
			<button
				type="button"
				class="flex h-9 items-center justify-center gap-1.5 rounded-full bg-[var(--wa-accent)] text-[12px] font-semibold text-[var(--wa-accent-ink)] transition-transform duration-150 active:scale-[0.97]"
				@click="emit('restart')"
			>
				<span class="lucide-rotate-cw size-3.5" aria-hidden="true" />
				{{ chrome.restartPreview }}
			</button>
			<div class="h-9 rounded-full bg-[var(--wa-sheet)]" aria-hidden="true" />
		</div>
	</div>
</template>
