import { isQuestion, type Block, type FlowModel, type Json, type JsonObject, type Screen } from "../model";

export type Value = string | string[] | boolean;

/** What the preview knows beyond the JSON: answers typed and data passed in, by screen uid. */
export interface Filled {
  form(screenUid: string): Record<string, Value> | undefined;
  data(screenUid: string): Record<string, Json> | undefined;
}

const REFERENCE = /\$\{(?:screen\.(\w+)\.)?(form|data)\.(\w+)\}/g;
const WHOLE_REFERENCE = new RegExp(`^${REFERENCE.source}$`);

export function isReference(text: string): boolean {
  return WHOLE_REFERENCE.test(text);
}

/**
 * Text as WhatsApp would show it: `${data.x}` reads the passed data or the screen's `__example__`,
 * `${form.x}` the answer, or `[its label]` until there is one.
 */
export function sampleText(text: unknown, model: FlowModel, screen: Screen, filled?: Filled): string {
  if (typeof text !== "string") return "";
  const plain = /^`[\s\S]*`$/.test(text) ? text.slice(1, -1) : text;
  return plain.replace(REFERENCE, (_match, screenId: string | undefined, scope: string, key: string) => {
    const on = screenId ? model.screens.find((each) => each.props.id === screenId) : screen;
    if (!on) return `[${key}]`;
    const value = resolve(on, scope as "form" | "data", key, filled);
    if (value !== undefined && value !== "") return value;
    return `[${scope === "form" ? (labelOf(on, key) ?? key) : key}]`;
  });
}

/** The value a reference holds, or undefined when the preview has none. Raw: option ids stay ids. */
export function referenceValue(reference: string, model: FlowModel, screen: Screen, filled?: Filled): Json | undefined {
  const match = WHOLE_REFERENCE.exec(reference);
  if (!match) return undefined;
  const [, screenId, scope, key] = match;
  const on = screenId ? model.screens.find((each) => each.props.id === screenId) : screen;
  if (!on) return undefined;
  if (scope === "form") return filled?.form(on.uid)?.[key] as Json | undefined;
  return filled?.data(on.uid)?.[key] ?? example(on, key);
}

/** A typed or chosen answer as the contact reads it: option titles, not ids. */
export function answerText(block: Block | undefined, value: Value | undefined): string {
  if (value === undefined || typeof value === "boolean") return value === undefined ? "" : String(value);
  const titles = optionTitles(block);
  const each = (id: string) => titles.get(id) ?? id;
  return Array.isArray(value) ? value.map(each).join(", ") : each(value);
}

export function questionNamed(screen: Screen, name: string): Block | undefined {
  return screen.blocks.find((block) => isQuestion(block) && block.component.name === name);
}

function resolve(screen: Screen, scope: "form" | "data", key: string, filled?: Filled): string | undefined {
  if (scope === "form") {
    const value = filled?.form(screen.uid)?.[key];
    return value === undefined ? undefined : answerText(questionNamed(screen, key), value);
  }
  const passed = filled?.data(screen.uid)?.[key];
  const value = passed !== undefined ? passed : example(screen, key);
  return value === undefined ? undefined : printable(value);
}

function example(screen: Screen, key: string): Json | undefined {
  const declared = (screen.props.data as JsonObject | undefined)?.[key] as JsonObject | undefined;
  return declared?.__example__;
}

function labelOf(screen: Screen, key: string): string | undefined {
  const label = questionNamed(screen, key)?.component.label;
  return typeof label === "string" && label ? label : undefined;
}

function optionTitles(block: Block | undefined): Map<string, string> {
  const options = block?.component["data-source"];
  if (!Array.isArray(options)) return new Map();
  return new Map(
    (options as JsonObject[]).map((option) => [String(option.id), String(option.title ?? option.id)])
  );
}

function printable(value: Json): string {
  if (value === null) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
