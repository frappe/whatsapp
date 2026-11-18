<script setup lang="ts">
import { Button } from "frappe-ui";
import { useMetaConnect } from "./useMetaConnect";

/** Renders nothing unless this site can connect with Meta (a Frappe Cloud v2 site). */
defineProps<{
	/** a WA Account to reconnect; without it the sign-in adds a new account */
	account?: string;
}>();

const meta = useMetaConnect();
</script>

<template>
	<Button
		v-if="meta.canConnect"
		:label="account ? 'Reconnect' : 'Connect with Meta'"
		:loading="meta.connecting"
		@click="meta.connect(account)"
	/>
</template>
