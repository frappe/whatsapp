import {
  detachAnswer,
  putFormValues,
  slug,
  takeFormValues,
  unique,
  uniqueAnswerKey,
} from "./answers";
import { BLOCK_KINDS, TEXT_TYPES, isAdvanced } from "./catalogue";
import { assign, blockOf, edit, landsInForm, newUid, screenOf } from "./edit";
import type { Added, Block, FlowModel, Json, JsonObject, Screen } from "./types";

/** Questions get an answer key from their text, unique in the Flow. */
export function addBlock(
  model: FlowModel,
  screenUid: string,
  type: string,
  { text = "", index }: { text?: string; index?: number } = {}
): Added {
  const kind = BLOCK_KINDS[type];
  if (!kind) throw new Error(`${type} is not in the block catalogue`);
  let uid = "";
  const changed = edit(model, (draft) => {
    const screen = screenOf(draft, screenUid);
    const at = index ?? screen.blocks.length;
    const component: JsonObject = kind.question
      ? { type, name: uniqueAnswerKey(draft, text), label: text }
      : { type, [kind.textKey]: text };
    uid = newUid(draft, "b");
    insertBlock(screen, { uid, component: { ...component, ...clone(kind.defaults) }, inForm: false }, at);
  });
  return { model: changed, uid };
}

/** Set or, with undefined, remove properties. The type and answer key have their own operations. */
export function updateBlock(
  model: FlowModel,
  uid: string,
  patch: Record<string, Json | undefined>
): FlowModel {
  if ("type" in patch || "name" in patch)
    throw new Error("Change the type or answer key with its own operation");
  return edit(model, (draft) => {
    const { block } = blockOf(draft, uid);
    if (isAdvanced(block)) throw new Error("Advanced blocks are edited in JSON");
    assign(block.component, patch);
  });
}

/** Meta's "Type" select: a heading, body or caption becomes another of them in place. */
export function changeTextType(model: FlowModel, uid: string, type: string): FlowModel {
  return edit(model, (draft) => {
    const { block } = blockOf(draft, uid);
    if (!TEXT_TYPES.includes(String(block.component.type)) || !TEXT_TYPES.includes(type))
      throw new Error("Only headings, body and caption convert into each other");
    block.component.type = type;
  });
}

/** Within its screen; `index` counts the screen's blocks without the moved one. */
export function moveBlock(model: FlowModel, uid: string, index: number): FlowModel {
  return edit(model, (draft) => {
    const { screen, block, index: at } = blockOf(draft, uid);
    const values = takeFormValues(screen, block);
    removeBlock(screen, at);
    insertBlock(screen, block, index);
    putFormValues(screen, block, values);
  });
}

/** A choice block's `data-source`, or none when it is a `${…}` reference. */
export function optionsOf(component: JsonObject): JsonObject[] {
  const source = component["data-source"];
  return Array.isArray(source) ? (source as JsonObject[]) : [];
}

export function deleteBlock(model: FlowModel, uid: string): FlowModel {
  return edit(model, (draft) => {
    const { screen, block, index } = blockOf(draft, uid);
    detachAnswer(draft, screen, block);
    removeBlock(screen, index);
  });
}

export function addOption(
  model: FlowModel,
  uid: string,
  option: { title: string; description?: string },
  index?: number
): FlowModel {
  return editOptions(model, uid, (options) => {
    const id = unique(slug(option.title, "option"), new Set(options.map((each) => String(each.id))));
    options.splice(index ?? options.length, 0, { id, ...option });
  });
}

/** The id stays when the title changes: answers already received carry it. */
export function updateOption(
  model: FlowModel,
  uid: string,
  index: number,
  patch: Record<string, Json | undefined>
): FlowModel {
  return editOptions(model, uid, (options) => assign(options[index], patch));
}

export function removeOption(model: FlowModel, uid: string, index: number): FlowModel {
  return editOptions(model, uid, (options) => options.splice(index, 1));
}

function editOptions(model: FlowModel, uid: string, change: (options: JsonObject[]) => void): FlowModel {
  return edit(model, (draft) => {
    const { block } = blockOf(draft, uid);
    if (isAdvanced(block) || !BLOCK_KINDS[String(block.component.type)].choices) {
      throw new Error("Only choice blocks have options");
    }
    change(block.component["data-source"] as JsonObject[]);
  });
}

function insertBlock(screen: Screen, block: Block, index: number) {
  block.inForm = landsInForm(screen, screen.blocks, index);
  screen.blocks.splice(index, 0, block);
}

/** The footer keeps its place by following the block before the removed one. */
function removeBlock(screen: Screen, index: number) {
  const [removed] = screen.blocks.splice(index, 1);
  if (screen.footer?.after === removed.uid) screen.footer.after = screen.blocks[index - 1]?.uid ?? null;
}

function clone(value: JsonObject): JsonObject {
  return JSON.parse(JSON.stringify(value));
}
