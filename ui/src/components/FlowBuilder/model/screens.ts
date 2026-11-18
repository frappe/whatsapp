import { FLOW_JSON_VERSION } from "./catalogue";
import { assign, edit, landsInForm, newUid, screenOf } from "./edit";
import { screenItems } from "./serialize";
import type { Added, FlowModel, Footer, FooterAction, JsonObject, Screen } from "./types";

export function createFlow(title = "Welcome"): FlowModel {
  const model: FlowModel = { flow: { version: FLOW_JSON_VERSION, screens: null }, screens: [], nextUid: 1 };
  return addScreen(model, { title }).model;
}

/** A new screen is an ending with a Continue button, so a Flow stays complete while it grows. */
export function addScreen(model: FlowModel, { title, index }: { title: string; index?: number }): Added {
  let uid = "";
  const changed = edit(model, (draft) => {
    uid = newUid(draft, "s");
    const id = uniqueScreenId(draft, title);
    const screen: Screen = {
      uid,
      props: { id, title, terminal: true, layout: null },
      layout: { type: "SingleColumnLayout", children: null },
      form: null,
      blocks: [],
      footer: newFooter(draft, "Continue", false),
    };
    draft.screens.splice(index ?? draft.screens.length, 0, screen);
  });
  return { model: changed, uid };
}

export function renameScreen(model: FlowModel, uid: string, title: string): FlowModel {
  return edit(model, (draft) => assign(screenOf(draft, uid).props, { title }));
}

/** Setting the action, "finish" included, makes the builder write the ending's answers again. */
export function setFooter(
  model: FlowModel,
  uid: string,
  { label, action }: { label?: string; action?: FooterAction }
): FlowModel {
  return edit(model, (draft) => {
    const screen = screenOf(draft, uid);
    const footer = (screen.footer ??= newFooter(
      draft,
      label ?? "Continue",
      landsInForm(screen, screenItems(screen), screen.blocks.length)
    ));
    if (label !== undefined) footer.component.label = label;
    if (action === undefined) return;
    footer.component["on-click-action"] = footerAction(
      footer.component["on-click-action"] as JsonObject,
      action
    );
    footer.customAnswers = false;
    if (action === "finish") screen.props.terminal = true;
    else assign(screen.props, { terminal: undefined, success: undefined });
    if (!("layout" in screen.props)) screen.props.layout = null;
    screen.layout ??= { type: "SingleColumnLayout", children: null };
  });
}

function newFooter(model: FlowModel, label: string, inForm: boolean): Footer {
  return {
    uid: newUid(model, "f"),
    component: { type: "Footer", label, "on-click-action": { name: "complete", payload: {} } },
    inForm,
    customAnswers: false,
  };
}

function footerAction(current: JsonObject | undefined, action: FooterAction): JsonObject {
  if (action === "finish") return { name: "complete", payload: {} };
  const payload = current?.name === "navigate" && current.payload ? current.payload : {};
  return { name: "navigate", next: { type: "screen", name: action.navigate }, payload };
}

function uniqueScreenId(model: FlowModel, title: string): string {
  const base =
    title
      .toUpperCase()
      .replace(/[^A-Z]+/g, "_")
      .replace(/^_+|_+$/g, "") || "SCREEN";
  const taken = new Set(model.screens.map((screen) => screen.props.id));
  let id = base;
  for (let suffix = 1; taken.has(id) || id === "SUCCESS"; suffix++) id = `${base}_${letters(suffix)}`;
  return id;
}

/** 1 → B, 25 → Z, 26 → BA: screen ids stay letters only. */
function letters(n: number): string {
  return (n >= 26 ? letters(Math.floor(n / 26)) : "") + String.fromCharCode(65 + (n % 26));
}
