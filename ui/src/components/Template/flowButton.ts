import { format, type FlowButtonChrome } from "./flowChrome";
import type {
  FlowInput,
  FlowOutline,
  ResponseAction,
  ResponseActionKind,
  ResponseMapping,
} from "./types";

/** Mirrors `MESSAGE_SOURCES` in `flows/template_validation.py`. Each is also its own source type. */
export const MESSAGE_SOURCES = [
  "sender_phone",
  "sender_name",
  "reference_doctype",
  "reference_name",
  "received_at",
  "whole_response",
] as const;

export const RESPONSE_ACTION_KINDS: ResponseActionKind[] = ["Update Reference", "Create Document"];

type Stored = string | unknown[] | null | undefined;

export function parseInputs(json: Stored): FlowInput[] {
  return parseList(json).map((row) => ({
    key: String(row.key ?? ""),
    source_field: String(row.source_field ?? ""),
  }));
}

export function serializeInputs(inputs: FlowInput[]): string {
  const mapped = inputs.filter((input) => input.source_field);
  return JSON.stringify(mapped.map(({ key, source_field }) => ({ key, source_field })));
}

export function parseActions(json: Stored): ResponseAction[] {
  return parseList(json).map((row) => ({
    action: row.action === "Create Document" ? "Create Document" : "Update Reference",
    doctype: row.doctype ? String(row.doctype) : "",
    condition: row.condition ? String(row.condition) : "",
    fields: (Array.isArray(row.fields) ? row.fields : []).map((field: Record<string, unknown>) => ({
      source: String(field?.source ?? ""),
      target_field: String(field?.target_field ?? ""),
    })),
  }));
}

/** Writes only the documented keys: `doctype` for Create Document, `condition` when set. */
export function serializeActions(actions: ResponseAction[]): string {
  return JSON.stringify(
    actions.map((action) => ({
      action: action.action,
      ...(action.action === "Create Document" ? { doctype: action.doctype ?? "" } : {}),
      ...(action.condition?.trim() ? { condition: action.condition.trim() } : {}),
      fields: action.fields.map(({ source, target_field }: ResponseMapping) => ({ source, target_field })),
    }))
  );
}

export function isMessageSource(source: string): boolean {
  return (MESSAGE_SOURCES as readonly string[]).includes(source);
}

/** The server's source type for a mapping: the message source itself, the answer's type, else `unknown`. */
export function sourceType(source: string, outline: FlowOutline | undefined): string {
  if (!source) return "";
  if (isMessageSource(source)) return source;
  return outline?.answers.find((answer) => answer.key === source)?.type ?? "unknown";
}

/** A source the Flow no longer sends. Without an outline nothing can be called stale. */
export function isStaleSource(source: string, outline: FlowOutline | undefined): boolean {
  if (!source || isMessageSource(source) || !outline?.screens.length) return false;
  return !outline.answers.some((answer) => answer.key === source);
}

export function actionTarget(action: ResponseAction, referenceDoctype: string | undefined) {
  return action.action === "Create Document" ? action.doctype : referenceDoctype;
}

/** One line for a collapsed Response action: "Update CRM Deal · 3 fields · when …". */
export function actionSummary(
  action: ResponseAction,
  referenceDoctype: string | undefined,
  chrome: FlowButtonChrome
): string {
  const parts = [kindSummary(action, referenceDoctype, chrome)];
  const count = action.fields.length;
  if (count) parts.push(count === 1 ? chrome.oneField : format(chrome.manyFields, count));
  if (action.condition?.trim()) parts.push(format(chrome.whenSummary, action.condition.trim()));
  return parts.join(" · ");
}

function kindSummary(action: ResponseAction, referenceDoctype: string | undefined, chrome: FlowButtonChrome) {
  if (action.action === "Create Document") {
    return action.doctype ? format(chrome.createSummary, action.doctype) : chrome.createSummaryNoDoctype;
  }
  return referenceDoctype ? format(chrome.updateSummary, referenceDoctype) : chrome.updateReferenceSummary;
}

function parseList(json: Stored): Record<string, any>[] {
  const value = typeof json === "string" ? parseJson(json) : json;
  return Array.isArray(value) ? value.filter((row) => row && typeof row === "object") : [];
}

function parseJson(json: string): unknown {
  try {
    return JSON.parse(json);
  } catch {
    return null;
  }
}
