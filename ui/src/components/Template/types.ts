/**
 * The `@whatsapp/ui` template contract: a `WhatsApp Template` document as `frappe.client.get`
 * returns it, under the DocType's own fieldnames.
 */

import type { MaybeRefOrGetter } from "vue";
import type { FieldMeta } from "@framework/ui/components/FormLayout";
import type { WhatsAppFlowStatus, WhatsAppTemplateButton } from "../Messages/types";
import type { FieldOption } from "../Account/types";
import type { FlowButtonChrome } from "./flowChrome";

export type TemplateType = "Utility" | "Marketing" | "Authentication";
export type TemplateHeaderType = "Text" | "Image" | "Document" | "GIF" | "Video";
export type TemplateStatus = "Pending" | "Approved" | "Rejected" | "Deleted";

export interface TemplateButtonRow extends WhatsAppTemplateButton {
  name?: string;
  idx?: number;
  /** a {@link FlowInput} list as a JSON string */
  flow_inputs?: string | FlowInput[] | null;
  /** a {@link ResponseAction} list as a JSON string */
  flow_response_actions?: string | ResponseAction[] | null;
  [key: string]: unknown;
}

/** One Flow input of a Flow button: the entry screen's `key`, filled from `source_field` of the reference document. */
export interface FlowInput {
  key: string;
  source_field: string;
}

export type ResponseActionKind = "Update Reference" | "Create Document";

/** One field of a Response action's map: an answer key or a message source, into a field of the target. */
export interface ResponseMapping {
  source: string;
  target_field: string;
}

/** One thing a Flow button does with a Flow response. */
export interface ResponseAction {
  action: ResponseActionKind;
  /** Create Document only */
  doctype?: string;
  /** optional Python expression over `response`, `doc` and `message` */
  condition?: string;
  fields: ResponseMapping[];
}

/** One `WA Flow` of the template's account, as the Flow picker lists it. */
export interface WhatsAppFlowOption {
  /** Meta's Flow ID */
  name: string;
  flow_name: string;
  status: WhatsAppFlowStatus;
  /** set when the Flow calls the business's own endpoint, which allows Data Exchange */
  endpoint_uri?: string | null;
  preview_url?: string | null;
}

/** One key a Flow's `complete` action sends. `type` keys the server's `SOURCE_FIELD_TYPES`. */
export interface FlowOutlineAnswer {
  key: string;
  label: string;
  component: string;
  type: string;
}

/** What the server read out of a Flow's JSON. No `screens` means the JSON was missing or invalid. */
export interface FlowOutline {
  screens: string[];
  /** entry screen id -> declared data key -> declared type */
  entry_screens: Record<string, Record<string, string>>;
  answers: FlowOutlineAnswer[];
  sensitive: string[];
}

/** A value the controller fetches once and caches. `retry()` fetches it again after a failure. */
export interface Loaded<T> {
  data: T | undefined;
  loading: boolean;
  error: unknown;
  retry(): void;
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
  doctype: "WA Template";
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
  theme: "amber" | "green" | "red" | "gray";
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
  /** fields of `doc.reference_doctype` a variable can name; empty until loaded, or when there is no doctype */
  fieldOptions: VariableItem[];
  /** Inserts or saves the whole document, then reloads it. Resolves to the docname, or null on failure. */
  save(): Promise<string | null>;
  reload(): Promise<void>;
  /** the Flows of the WhatsApp Business Account of `doc.whatsapp_account`; null while there is no account */
  flows: Loaded<WhatsAppFlowOption[]> | null;
  /** Fetches the Flows and their outlines again, keeping the form's edits, e.g. after the Flow builder closes. */
  refreshFlows(): void;
  /** one Flow's outline, cached per Flow */
  outline(flow: string | undefined): Loaded<FlowOutline> | null;
  /** fields of the reference DocType that can fill a Flow input declared as `declaredType` */
  inputSourceFields(referenceDoctype: string | undefined, declaredType: string): Loaded<FieldOption[]> | null;
  /** fields of `targetDoctype` that can hold a source of `sourceType` */
  mappableFields(targetDoctype: string | undefined, sourceType: string): Loaded<FieldOption[]> | null;
}

export interface TemplateFormProps {
  controller: TemplateController;
  /** Chrome for every Flow button's editor */
  flowChrome?: Partial<FlowButtonChrome>;
  /** passed on to every Flow button's editor */
  onNewFlow?: () => void;
  onEditFlow?: (flow: string) => void;
}

/** Configures one Flow button row: its Flow, inputs and Response actions. Draws content, not its container. */
export interface FlowButtonEditorProps {
  controller: TemplateController;
  /** the button row; the editor writes to it in place, as a grid cell does */
  button: TemplateButtonRow;
  disabled?: boolean;
  chrome?: Partial<FlowButtonChrome>;
  /**
   * `@new-flow` shows "New flow" under the Flow picker's options; `@edit-flow` shows "Edit flow"
   * beside its label once a Flow is chosen. Props, not emits, so each shows only when the host listens.
   */
  onNewFlow?: () => void;
  onEditFlow?: (flow: string) => void;
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
  fields: () => VariableItem[];
}

export type TemplateVariablesFieldProps = TemplateBodyEditorProps;

/** A field of the reference DocType: `{{value}}` in the text, shown to the user as `label`. */
export interface VariableItem {
  value: string;
  label: string;
}
