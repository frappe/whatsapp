import { isAdvanced, isQuestion } from "./catalogue";
import { blockOf, edit, isEntry, mapStrings } from "./edit";
import { screenItems } from "./serialize";
import type { Block, FlowModel, Json, JsonObject, Screen } from "./types";

const DATA_REFERENCE = /^\$\{data\.(\w+)\}$/;

/** "Full name" → `full_name`. */
export function answerKey(text: string): string {
  return slug(text, "answer");
}

export function uniqueAnswerKey(model: FlowModel, text: string): string {
  return unique(answerKey(text), answerKeys(model));
}

/** References to the old key follow it. Custom answers keep their own payload keys. */
export function renameAnswerKey(model: FlowModel, uid: string, key: string): FlowModel {
  return edit(model, (draft) => {
    const { screen, block } = editableQuestion(draft, uid);
    const old = String(block.component.name);
    block.component.name = key;
    const sensitive = screen.props.sensitive;
    if (Array.isArray(sensitive))
      screen.props.sensitive = sensitive.map((name) => (name === old ? key : name));
    if (screen.form) renameFormKey(screen.form, old, key);
    for (const each of draft.screens) {
      const references = each === screen ? [`\${form.${old}}`, `\${form.${key}}`] : [];
      references.push(
        `\${screen.${screen.props.id}.form.${old}}`,
        `\${screen.${screen.props.id}.form.${key}}`
      );
      for (const item of screenItems(each)) {
        item.component = mapStrings(item.component, (text) => replacePairs(text, references)) as JsonObject;
      }
    }
  });
}

/** "Hide in chat": the screen's `sensitive` list. */
export function setSensitive(model: FlowModel, uid: string, sensitive: boolean): FlowModel {
  return edit(model, (draft) => {
    const { screen, block } = editableQuestion(draft, uid);
    const name = String(block.component.name);
    if (sensitive) addSensitive(screen, name);
    else removeSensitive(screen, name);
  });
}

export function isSensitive(screen: Screen, block: Block): boolean {
  const sensitive = screen.props.sensitive;
  return Array.isArray(sensitive) && sensitive.includes(String(block.component.name));
}

/**
 * Prefill from template: the entry screen declares `data.<key>` with an `__example__`, and the
 * question starts at `${data.<key>}` (`init-value`, or the Form's `init-values` inside a Form).
 */
export function setPrefill(
  model: FlowModel,
  uid: string,
  { key, example }: { key?: string; example: Json }
): FlowModel {
  return edit(model, (draft) => {
    const { screen, block } = editableQuestion(draft, uid);
    if (!isEntry(draft, screen)) throw new Error("Only the first screen can be prefilled");
    const dataKey = key ?? String(block.component.name);
    const previous = prefillKey(screen, block);
    if (previous && previous !== dataKey) dropUnusedData(draft, screen, previous, block);
    const data = (screen.props.data ??= {}) as JsonObject;
    data[dataKey] = { ...declaredType(block.component), __example__: example };
    setInitValue(screen, block, `\${data.${dataKey}}`);
  });
}

export function clearPrefill(model: FlowModel, uid: string): FlowModel {
  return edit(model, (draft) => {
    const { screen, block } = editableQuestion(draft, uid);
    const key = prefillKey(screen, block);
    setInitValue(screen, block, undefined);
    if (key) dropUnusedData(draft, screen, key);
  });
}

/** The data key a question is prefilled from, when the screen declares it. */
export function prefillKey(screen: Screen, block: Block): string | undefined {
  const match = DATA_REFERENCE.exec(String(initValue(screen, block) ?? ""));
  const data = screen.props.data as JsonObject | undefined;
  return match && data && match[1] in data ? match[1] : undefined;
}

export interface FormValues {
  initValue?: Json;
  errorMessage?: Json;
}

export interface DetachedAnswer extends FormValues {
  sensitive: boolean;
  data?: [string, Json];
}

/** Take a question's screen-level settings off its screen, before it moves away or is deleted. */
export function detachAnswer(model: FlowModel, screen: Screen, block: Block): DetachedAnswer {
  const name = String(block.component.name ?? "");
  if (!name || isAdvanced(block)) return { sensitive: false };
  const key = prefillKey(screen, block);
  const detached: DetachedAnswer = {
    sensitive: isSensitive(screen, block),
    ...takeFormValues(screen, block),
  };
  if (key) {
    detached.data = [key, (screen.props.data as JsonObject)[key]];
    dropUnusedData(model, screen, key, block);
  }
  removeSensitive(screen, name);
  return detached;
}

export function attachAnswer(screen: Screen, block: Block, detached: DetachedAnswer) {
  const name = String(block.component.name ?? "");
  if (!name || isAdvanced(block)) return;
  if (detached.sensitive) addSensitive(screen, name);
  if (detached.data) ((screen.props.data ??= {}) as JsonObject)[detached.data[0]] = detached.data[1];
  putFormValues(screen, block, detached);
}

/** A Form keeps its questions' start values and errors in `init-values` and `error-messages`. */
export function takeFormValues(screen: Screen, block: Block): FormValues {
  const name = String(block.component.name ?? "");
  if (!name || !block.inForm || !screen.form || isAdvanced(block)) return {};
  return {
    initValue: takeKey(screen.form, "init-values", name),
    errorMessage: takeKey(screen.form, "error-messages", name),
  };
}

/** Meta takes `init-value` and `error-message` only outside a Form. */
export function putFormValues(screen: Screen, block: Block, values: FormValues) {
  if (!block.component.name || isAdvanced(block)) return;
  const initValue = values.initValue ?? block.component["init-value"];
  const errorMessage = values.errorMessage ?? block.component["error-message"];
  if (initValue !== undefined) setFormValue(screen, block, "init-values", "init-value", initValue);
  if (errorMessage !== undefined)
    setFormValue(screen, block, "error-messages", "error-message", errorMessage);
}

export function slug(text: string, fallback: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || fallback
  );
}

export function unique(base: string, taken: Set<string>): string {
  let value = base;
  for (let suffix = 2; taken.has(value); suffix++) value = `${base}_${suffix}`;
  return value;
}

function answerKeys(model: FlowModel): Set<string> {
  return new Set(
    model.screens.flatMap((screen) =>
      screen.blocks.filter(isQuestion).map((block) => String(block.component.name))
    )
  );
}

function editableQuestion(model: FlowModel, uid: string) {
  const found = blockOf(model, uid);
  if (!isQuestion(found.block)) throw new Error("Only questions have answers");
  return found;
}

function initValue(screen: Screen, block: Block): Json | undefined {
  if (block.inForm && screen.form) {
    return ((screen.form["init-values"] as JsonObject | undefined) ?? {})[String(block.component.name)];
  }
  return block.component["init-value"];
}

function setInitValue(screen: Screen, block: Block, value: Json | undefined) {
  setFormValue(screen, block, "init-values", "init-value", value);
}

function setFormValue(
  screen: Screen,
  block: Block,
  formKey: string,
  componentKey: string,
  value: Json | undefined
) {
  const name = String(block.component.name);
  if (block.inForm && screen.form) {
    delete block.component[componentKey];
    if (value === undefined) takeKey(screen.form, formKey, name);
    else ((screen.form[formKey] ??= {}) as JsonObject)[name] = value;
  } else if (value === undefined) {
    delete block.component[componentKey];
  } else {
    block.component[componentKey] = value;
  }
}

function takeKey(form: JsonObject, mapKey: string, name: string): Json | undefined {
  const map = form[mapKey] as JsonObject | undefined;
  if (!map || !(name in map)) return undefined;
  const value = map[name];
  delete map[name];
  if (!Object.keys(map).length) delete form[mapKey];
  return value;
}

function renameFormKey(form: JsonObject, old: string, key: string) {
  for (const mapKey of ["init-values", "error-messages"]) {
    const map = form[mapKey] as JsonObject | undefined;
    if (map && old in map)
      form[mapKey] = Object.fromEntries(Object.entries(map).map(([k, v]) => [k === old ? key : k, v]));
  }
}

function addSensitive(screen: Screen, name: string) {
  const sensitive = (screen.props.sensitive ??= []) as Json[];
  if (!sensitive.includes(name)) sensitive.push(name);
}

function removeSensitive(screen: Screen, name: string) {
  const sensitive = screen.props.sensitive;
  if (!Array.isArray(sensitive) || !sensitive.includes(name)) return;
  screen.props.sensitive = sensitive.filter((each) => each !== name);
  if (!(screen.props.sensitive as Json[]).length) delete screen.props.sensitive;
}

/** Remove a data declaration nothing but `except` reads. */
function dropUnusedData(model: FlowModel, screen: Screen, key: string, except?: Block) {
  const own = `\${data.${key}}`;
  const global = `\${screen.${screen.props.id}.data.${key}}`;
  const reads = (each: Screen, json: Json) => {
    const text = JSON.stringify(json);
    return text.includes(global) || (each === screen && text.includes(own));
  };
  const used = model.screens.some(
    (each) =>
      screenItems(each).some((item) => item !== except && reads(each, item.component)) ||
      (each.form !== null && reads(each, each.form))
  );
  if (used) return;
  const data = screen.props.data as JsonObject;
  delete data[key];
  if (!Object.keys(data).length) delete screen.props.data;
}

function declaredType(component: JsonObject): JsonObject {
  switch (component.type) {
    case "CheckboxGroup":
    case "ChipsSelector":
      return { type: "array", items: { type: "string" } };
    case "OptIn":
      return { type: "boolean" };
    case "TextInput":
      return { type: component["input-type"] === "number" ? "number" : "string" };
    default:
      return { type: "string" };
  }
}

function replacePairs(text: string, references: string[]): string {
  for (let i = 0; i < references.length; i += 2) text = text.replaceAll(references[i], references[i + 1]);
  return text;
}
