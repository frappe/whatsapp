import type { Component } from "vue";
import LucideFileText from "~icons/lucide/file-text";
import LucideMegaphone from "~icons/lucide/megaphone";
import LucideStar from "~icons/lucide/star";

/** Lucide stand-ins for the three icons WhatsApp draws on a Flow button. */
export const FLOW_ICONS: Record<"Document" | "Promotion" | "Review", Component> = {
	Document: LucideFileText,
	Promotion: LucideMegaphone,
	Review: LucideStar,
};
