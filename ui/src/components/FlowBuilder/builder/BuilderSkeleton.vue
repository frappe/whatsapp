<script setup lang="ts">
import { Skeleton } from "frappe-ui";
</script>

<template>
	<div class="flex h-full min-h-0 flex-col" aria-busy="true">
		<div class="flex h-12 shrink-0 items-center gap-3 border-b border-outline-gray-1 px-3">
			<Skeleton class="h-4 w-48 rounded-4" />
			<div class="flex-1" />
			<Skeleton class="h-7 w-[5.75rem] rounded-4" />
		</div>
		<div class="grid min-h-0 flex-1 grid-cols-2 divide-x divide-outline-gray-1">
			<div class="flex flex-col gap-2 p-5">
				<Skeleton class="mb-2 h-4 w-20 rounded-4" />
				<Skeleton v-for="i in 2" :key="i" class="h-9 rounded-4" />
				<Skeleton class="mb-2 mt-6 h-4 w-28 rounded-4" />
				<Skeleton v-for="i in 5" :key="`row${i}`" class="h-9 rounded-5" />
			</div>
			<div class="flex items-center justify-center p-5">
				<Skeleton class="h-[540px] w-[326px] rounded-[24px]" />
			</div>
		</div>
	</div>
</template>
