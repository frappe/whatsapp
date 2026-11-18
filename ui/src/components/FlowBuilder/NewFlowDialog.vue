<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { Button, Dialog, ErrorMessage, MultiSelect, Select, TextInput } from "frappe-ui";
import { useChrome } from "./context";
import { fieldOfError } from "./session";
import type { FlowCategory, NewFlowDialogProps } from "./types";
import { serverErrorMessage } from "../../utils/serverError";

const props = defineProps<NewFlowDialogProps>();
const emit = defineEmits<{ created: [name: string] }>();
const open = defineModel<boolean>("open", { default: false });

const CATEGORIES: FlowCategory[] = [
	"LEAD_GENERATION",
	"SIGN_UP",
	"SIGN_IN",
	"APPOINTMENT_BOOKING",
	"CONTACT_US",
	"CUSTOMER_SUPPORT",
	"SURVEY",
	"OTHER",
];

const chrome = useChrome(() => props.chrome);
const form = reactive({ flow_name: "", categories: [] as FlowCategory[], source: "" });
const errors = reactive({ flow_name: "", categories: "", other: "" });
const creating = ref(false);

const categoryOptions = computed(() =>
	CATEGORIES.map((value) => ({ value, label: chrome.value[value] }))
);
const sourceOptions = computed(() => [
	{ value: "", label: chrome.value.startBlank },
	...props.controller.rows.map((row) => ({
		value: row.name,
		label: row.flow_name,
		description: chrome.value[row.status],
	})),
]);

watch(open, (isOpen) => {
	if (!isOpen) return;
	Object.assign(form, { flow_name: "", categories: [], source: "" });
	clearErrors();
});

function clearErrors() {
	Object.assign(errors, { flow_name: "", categories: "", other: "" });
}

function validate(): boolean {
	clearErrors();
	if (!form.flow_name.trim()) errors.flow_name = chrome.value.nameRequired;
	if (!form.categories.length) errors.categories = chrome.value.categoriesRequired;
	return !errors.flow_name && !errors.categories;
}

async function submit() {
	if (creating.value || !validate()) return;
	creating.value = true;
	try {
		const name = await props.controller.create({
			account: props.account,
			flow_name: form.flow_name.trim(),
			categories: form.categories,
			...(form.source ? { clone_from: form.source } : {}),
		});
		open.value = false;
		emit("created", name);
	} catch (e) {
		errors[fieldOfError(e) ?? "other"] = serverErrorMessage(e);
	} finally {
		creating.value = false;
	}
}
</script>

<template>
	<Dialog v-model:open="open" :title="chrome.newFlowTitle" size="md">
		<template #default>
			<form class="flex flex-col gap-4" @submit.prevent="submit">
				<TextInput
					v-model="form.flow_name"
					:label="chrome.nameLabel"
					:placeholder="chrome.namePlaceholder"
					:error="errors.flow_name"
					required
					autofocus
					@update:model-value="errors.flow_name = ''"
				/>
				<MultiSelect
					v-model="form.categories"
					:label="chrome.categoriesLabel"
					:description="errors.categories ? undefined : chrome.categoriesDescription"
					:error="errors.categories"
					:placeholder="chrome.categoriesPlaceholder"
					:options="categoryOptions"
					hide-search
					required
					@update:model-value="errors.categories = ''"
				/>
				<Select
					v-model="form.source"
					:label="chrome.startLabel"
					:options="sourceOptions"
				/>
				<ErrorMessage v-if="errors.other" :message="errors.other" />
				<button type="submit" class="hidden" />
			</form>
		</template>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button :label="chrome.cancel" @click="open = false" />
				<Button
					variant="solid"
					:label="chrome.create"
					:loading="creating"
					@click="submit"
				/>
			</div>
		</template>
	</Dialog>
</template>
