/**
 * The `@whatsapp/ui` account contract: a `WhatsApp Account` document as `frappe.client.get`
 * returns it, under the DocType's own fieldnames.
 */

import type { MaybeRefOrGetter } from "vue";

export type AppendTrigger = "Incoming" | "Outgoing" | "Both";

/** The four mapping slots on an append action, each naming a field on `append_to`. */
export type MappingSlot =
  "message_field" | "sender_field" | "sender_name_field" | "timestamp_field";

export const MAPPING_SLOTS: readonly MappingSlot[] = [
  "message_field",
  "sender_field",
  "sender_name_field",
  "timestamp_field",
];

/** One `WhatsApp Account Append` row. */
export interface AppendAction {
  /** docname once saved; a new row has none until the first save */
  name?: string;
  append_to: string;
  trigger_on: AppendTrigger;
  message_field?: string;
  sender_field?: string;
  sender_name_field?: string;
  timestamp_field?: string;
  idx?: number;
  [key: string]: unknown;
}

export interface WhatsAppAccount {
  doctype: "WhatsApp Account";
  /** docname; absent on an account that has not been created yet */
  name?: string;
  account_name?: string;
  status?: "Active" | "Inactive";
  app_id?: string;
  business_id?: string;
  phone_id?: string;
  /**
   * Arrives masked (`*****`) and must go back untouched: Frappe reads that as "unchanged",
   * an empty value as "delete the stored token", anything else as a new token.
   */
  access_token?: string;
  auto_read_receipts?: 0 | 1;
  append_actions: AppendAction[];
  modified?: string;
  [key: string]: unknown;
}

/** One entry from `get_append_field_options`, in the shape Combobox takes. */
export interface FieldOption {
  label: string;
  value: string;
  description?: string;
}

export interface UseAccountOptions {
  /** Account to load. Empty or absent renders a blank account that `save()` creates. */
  name?: MaybeRefOrGetter<string | undefined>;
}

/**
 * The account controller: one document, its save, and the per-doctype option lists the
 * append action mappings choose from.
 */
export interface AccountController {
  doc: WhatsAppAccount;
  loading: boolean;
  saving: boolean;
  isDirty: boolean;
  /** true until the first successful save creates the record */
  isNew: boolean;
  /** the last load or save failure, cleared when the next one starts */
  error: unknown;
  /** Inserts or saves the whole document, then reloads it. Resolves to the docname, or null on failure. */
  save(): Promise<string | null>;
  reload(): Promise<void>;
  /** Blanks the row's four mapping slots and loads the options for the new doctype. */
  setAppendTo(row: AppendAction, doctype: string | null): Promise<void>;
  /** Options for one slot on one doctype; empty until loaded. Shared by every row on that doctype. */
  optionsFor(doctype: string | undefined, slot: MappingSlot): FieldOption[];
}

export interface AccountFormProps {
  controller: AccountController;
}

export interface AppendActionsTableProps {
  controller: AccountController;
}
