import type { Block, FlowModel, Footer, Json, JsonObject, Screen } from "./types";

/**
 * Every operation is pure: it edits a copy and returns it. A plain JSON copy also works on a
 * Vue reactive proxy, where `structuredClone` throws.
 */
export function edit(model: FlowModel, change: (draft: FlowModel) => void): FlowModel {
  const draft: FlowModel = JSON.parse(JSON.stringify(model));
  change(draft);
  return draft;
}

export function newUid(model: FlowModel, prefix: string): string {
  return `${prefix}${model.nextUid++}`;
}

export function screenOf(model: FlowModel, uid: string): Screen {
  const screen = model.screens.find((candidate) => candidate.uid === uid);
  if (!screen) throw new Error(`No screen ${uid}`);
  return screen;
}

export function blockOf(model: FlowModel, uid: string): { screen: Screen; block: Block; index: number } {
  for (const screen of model.screens) {
    const index = screen.blocks.findIndex((block) => block.uid === uid);
    if (index >= 0) return { screen, block: screen.blocks[index], index };
  }
  throw new Error(`No block ${uid}`);
}

export function isEntry(model: FlowModel, screen: Screen): boolean {
  return model.screens[0] === screen;
}

/** Set or, with undefined, remove keys. A new key goes last, an existing one keeps its place. */
export function assign(target: JsonObject, patch: Record<string, Json | undefined>) {
  for (const [key, value] of Object.entries(patch)) {
    if (value === undefined) delete target[key];
    else target[key] = value;
  }
}

/** A Form-wrapped screen puts a new item in the Form when it lands next to one that is. */
export function landsInForm(screen: Screen, items: (Block | Footer)[], index: number): boolean {
  if (!screen.form) return false;
  if (!items.some((item) => item.inForm)) return true;
  return Boolean(items[index - 1]?.inForm || items[index]?.inForm);
}

export function mapStrings(value: Json, change: (text: string) => string): Json {
  if (typeof value === "string") return change(value);
  if (Array.isArray(value)) return value.map((item) => mapStrings(item, change));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, mapStrings(item, change)]));
  }
  return value;
}

/** Visit every object in a JSON value, depth first. */
export function* objects(value: Json): Generator<JsonObject> {
  if (Array.isArray(value)) {
    for (const item of value) yield* objects(item);
  } else if (value && typeof value === "object") {
    yield value;
    for (const item of Object.values(value)) yield* objects(item);
  }
}
