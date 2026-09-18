/**
 * The `@whatsapp/ui` template contract: a `WhatsApp Template` document as `frappe.client.get`
 * returns it, under the DocType's own fieldnames.
 */

import type { MaybeRefOrGetter } from "vue";
import type { FieldMeta } from "@framework/ui/components/FormLayout";
import type { WhatsAppTemplateButton } from "../Messages/types";

export type TemplateType = "Utility" | "Marketing" | "Authentication";
export type TemplateHeaderType = "Text" | "Image" | "Document" | "GIF" | "Video";
export type TemplateStatus = "Pending" | "Approved" | "Rejected" | "Deleted";

export interface TemplateButtonRow extends WhatsAppTemplateButton {
  name?: string;
  idx?: number;
  [key: string]: unknown;
}

/** One `Template Variable` row: a `{{variable_name}}` in the text and the example Meta reviews it with. */
export interface TemplateVariableRow {
  name?: string;
  variable_name: string;
  variable_example: string;
  /** fieldname on `reference_doctype` that fills it when sent; derived on save */
  variable_field?: string;
  idx?: number;
  [key: string]: unknown;
}

export interface WhatsAppTemplateDoc {
  doctype: "WhatsApp Template";
  /** docname; absent on a template that has not been created yet */
  name?: string;
  template_label?: string;
  /** derived from the label by the server, and locked once Meta has it */
  template_name?: string;
  template_type?: TemplateType;
  /** Meta forbids changing it after creation */
  language?: string;
  whatsapp_account?: string;
  header_type?: TemplateHeaderType;
  header_text?: string;
  header_media?: string;
  message?: string;
  footer?: string;
  reference_doctype?: string;
  template_variables: TemplateVariableRow[];
  buttons: TemplateButtonRow[];
  status?: TemplateStatus;
  whatsapp_template_id?: string;
  modified?: string;
  [key: string]: unknown;
}

export interface UseTemplateOptions {
  /** Template to load. Empty or absent renders a blank template that `save()` creates. */
  name?: MaybeRefOrGetter<string | undefined>;
}

/** The one badge a host shows beside the title: `Not Saved`, or else the Meta status. */
export interface TemplateIndicator {
  label: string;
  theme: "orange" | "green" | "red" | "gray";
}

/**
 * The template controller: one document, its save, and the fieldnames of its reference
 * DocType that a `{{variable}}` may name.
 */
export interface TemplateController {
  doc: WhatsAppTemplateDoc;
  loading: boolean;
  saving: boolean;
  isDirty: boolean;
  /** true until the first successful save creates the record */
  isNew: boolean;
  indicator: TemplateIndicator | null;
  /** false once Meta holds the template in a state it refuses to edit */
  editable: boolean;
  /** why the template cannot be edited; null when it can */
  lockReason: string | null;
  /** the last load or save failure, cleared when the next one starts */
  error: unknown;
  /** fieldnames of `doc.reference_doctype`; empty until loaded, or when there is no doctype */
  fieldOptions: string[];
  /** Inserts or saves the whole document, then reloads it. Resolves to the docname, or null on failure. */
  save(): Promise<string | null>;
  reload(): Promise<void>;
}

export interface TemplateFormProps {
  controller: TemplateController;
}

/** The message as the contact will read it, with the variables' examples filled in. */
export interface TemplatePreviewProps {
  controller: TemplateController;
}

/** What `FormLayout` hands a field control, plus the `ui.props` the layout adds. */
export interface TemplateBodyEditorProps {
  field: FieldMeta;
  modelValue: unknown;
  /** read on every keystroke after `{{`, so a getter keeps it live */
  fields: () => string[];
}

export interface VariableItem {
  value: string;
}
