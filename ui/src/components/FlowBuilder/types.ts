import type { WhatsAppFlowStatus } from "../Messages/types";
import type { MetaValidationError } from "./model";
import type { FlowBuilderChrome } from "./chrome";

/** In the order the New flow dialog lists them. */
export const FLOW_CATEGORIES = [
  "LEAD_GENERATION",
  "SIGN_UP",
  "SIGN_IN",
  "APPOINTMENT_BOOKING",
  "CONTACT_US",
  "CUSTOMER_SUPPORT",
  "SURVEY",
  "OTHER",
] as const;

export type FlowCategory = (typeof FLOW_CATEGORIES)[number];

/** One row of `get_flow_list`. */
export interface FlowListRow {
  name: string;
  flow_name: string;
  status: WhatsAppFlowStatus;
  categories: FlowCategory[];
  modified: string;
  /** Templates whose Flow buttons open this Flow. */
  used_by: number;
}

export interface TemplateRef {
  name: string;
  template_label: string;
}

/** `get_flow_for_builder`. */
export interface BuilderFlow {
  name: string;
  flow_name: string;
  flow_json: string | Record<string, unknown> | null;
  status: WhatsAppFlowStatus;
  business_id: string;
  modified: string;
  validation_errors: MetaValidationError[];
  /** Answer key → templates whose Response actions map it. */
  used_keys: Record<string, TemplateRef[]>;
  /** Entry screen data key → templates whose Flow inputs fill it. */
  used_inputs: Record<string, TemplateRef[]>;
}

/** `save_flow` and `publish_flow`. */
export interface FlowState {
  status: WhatsAppFlowStatus;
  modified: string;
  validation_errors: MetaValidationError[];
}

export interface CreateFlowArgs {
  account: string;
  flow_name: string;
  categories: FlowCategory[];
  clone_from?: string;
}

/** The server methods the builder calls. A host or a story can pass its own. */
export interface FlowBuilderApi {
  list(account?: string): Promise<FlowListRow[]>;
  get(name: string): Promise<BuilderFlow>;
  create(args: CreateFlowArgs): Promise<string>;
  copy(name: string, flowName: string): Promise<string>;
  save(name: string, flowJson: string, modified: string): Promise<FlowState>;
  remove(name: string): Promise<void>;
  publish(name: string): Promise<FlowState>;
  sync(account: string): Promise<unknown>;
}

export interface Selection {
  screen: string | null;
  block: string | null;
}

/** How the phone preview is drawn. Interactive mode moves through the screens like a contact would. */
export interface PreviewSettings {
  interactive: boolean;
  theme: "light" | "dark";
}

export type SaveState = "saved" | "saving" | "failed" | "conflict";

export interface FlowBuilderProps {
  controller: import("./session").BuilderSession;
  chrome?: Partial<FlowBuilderChrome>;
}

export interface FlowListProps {
  controller: import("./listSession").FlowListSession;
  /** Offers Delete on Draft Flows. The server checks the permission again. */
  canWrite?: boolean;
  chrome?: Partial<FlowBuilderChrome>;
}

export interface NewFlowDialogProps {
  controller: import("./listSession").FlowListSession;
  /** The account a blank Flow is created in. */
  account: string;
  chrome?: Partial<FlowBuilderChrome>;
}
