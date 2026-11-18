import type { WhatsAppFlowStatus } from "../Messages/types";

/**
 * Meta's Flows list in WhatsApp Manager, where a Flow's health explains a block or throttle.
 * Unverified: no public reference documents this URL.
 */
export function whatsappManagerFlowsUrl(businessId: string): string {
  return `https://business.facebook.com/wa/manage/flows/?waba_id=${encodeURIComponent(businessId)}`;
}

export const STATUS_THEME: Record<WhatsAppFlowStatus, "green" | "gray" | "amber" | "red"> = {
  Draft: "gray",
  Published: "green",
  Throttled: "amber",
  Blocked: "red",
  Deprecated: "gray",
};
