import { describe, expect, it } from "vitest";
import {
  addReadMore,
  addScreen,
  deleteBlock,
  parse,
  setFooter,
  type FlowModel,
} from "../../src/components/FlowBuilder/model";
import { PreviewRun } from "../../src/components/FlowBuilder/preview/interactive";
import { flowJson } from "./fixtures";

function feedback(): FlowModel {
  return parse(flowJson("meta", "playground_feedback"));
}

function ids(run: PreviewRun) {
  return run.screen?.props.id;
}

function rateAll(run: PreviewRun) {
  for (const name of ["Purchase_experience", "Delivery_and_setup", "Customer_service"]) run.set(name, "1_Good");
}

describe("PreviewRun", () => {
  it("starts on the first screen of the journey", () => {
    const run = new PreviewRun(feedback());
    run.start();
    expect(ids(run)).toBe("RECOMMEND");
    expect(run.progress).toEqual({ step: 1, total: 2 });
    expect(run.sent).toBe(false);
    expect(run.canGoBack).toBe(false);
  });

  it("keeps the button off until every required question has an answer", () => {
    const run = new PreviewRun(feedback());
    run.start();
    expect(run.canContinue).toBe(false);
    run.set("Leave_a_comment", "Great");
    expect(run.canContinue).toBe(false);
    run.set("Choose_one", "0_Yes");
    expect(run.canContinue).toBe(true);
    run.set("Choose_one", "");
    expect(run.canContinue).toBe(false);
  });

  it("goes to the next screen, passing the answers its button sends", () => {
    const run = new PreviewRun(feedback());
    run.start();
    run.set("Choose_one", "0_Yes");
    run.continue();
    expect(ids(run)).toBe("RATE");
    expect(run.progress).toEqual({ step: 2, total: 2 });
    expect(run.canGoBack).toBe(true);
    expect(run.data(run.screen!.uid)).toEqual({ screen_0_Choose_one_0: "0_Yes", screen_0_Leave_a_comment_1: "" });
  });

  it("does not move while an answer is missing", () => {
    const run = new PreviewRun(feedback());
    run.start();
    run.continue();
    expect(ids(run)).toBe("RECOMMEND");
  });

  it("finishes on the last screen, and Restart starts again with nothing filled", () => {
    const run = new PreviewRun(feedback());
    run.start();
    run.set("Choose_one", "1_No");
    run.continue();
    rateAll(run);
    run.continue();
    expect(run.sent).toBe(true);
    run.restart();
    expect(run.sent).toBe(false);
    expect(ids(run)).toBe("RECOMMEND");
    expect(run.value("Choose_one")).toBeUndefined();
  });

  it("goes back with the answers kept", () => {
    const run = new PreviewRun(feedback());
    run.start();
    run.set("Choose_one", "0_Yes");
    run.continue();
    run.back();
    expect(ids(run)).toBe("RECOMMEND");
    expect(run.value("Choose_one")).toBe("0_Yes");
    expect(run.canGoBack).toBe(false);
  });

  it("follows the button's own target when the JSON is not in list order", () => {
    const base = feedback();
    const extra = addScreen(base, { title: "Extra" });
    const extraId = extra.model.screens.find((screen) => screen.uid === extra.uid)!.props.id as string;
    const model = setFooter(extra.model, base.screens[0].uid, { action: { navigate: extraId } });
    const run = new PreviewRun(model);
    run.start();
    run.set("Choose_one", "0_Yes");
    run.continue();
    expect(ids(run)).toBe(extraId);
  });

  it("keeps answers whose questions are still there after an edit, and drops the others", () => {
    const model = feedback();
    const run = new PreviewRun(model);
    run.start();
    run.set("Choose_one", "0_Yes");
    run.set("Leave_a_comment", "Great");
    const comment = model.screens[0].blocks.find((block) => block.component.name === "Leave_a_comment")!;
    run.sync(deleteBlock(model, comment.uid));
    expect(run.value("Choose_one")).toBe("0_Yes");
    expect(run.value("Leave_a_comment")).toBeUndefined();
    expect(ids(run)).toBe("RECOMMEND");
  });

  it("returns to the first screen when the current one is deleted", () => {
    const model = feedback();
    const run = new PreviewRun(model);
    run.show(model.screens[1].uid);
    const without = { ...model, screens: [model.screens[0]] };
    run.sync(without);
    expect(ids(run)).toBe("RECOMMEND");
  });

  it("shows any screen without moving through the journey", () => {
    const model = feedback();
    const run = new PreviewRun(model);
    run.show(model.screens[1].uid);
    expect(ids(run)).toBe("RATE");
    expect(run.canGoBack).toBe(false);
  });

  it("starts a question from its init-value: the example, or what the button passed", () => {
    const model = feedback();
    const comment = { type: "TextInput", name: "said", label: "You said", "init-value": "${data.screen_0_Choose_one_0}" };
    model.screens[1].blocks.unshift({ uid: "b-said", component: comment, inForm: true });
    const shown = new PreviewRun(model);
    shown.show(model.screens[1].uid);
    expect(shown.value("said")).toBe("Example");
    const run = new PreviewRun(model);
    run.start();
    run.set("Choose_one", "1_No");
    run.continue();
    expect(run.value("said")).toBe("1_No");
  });

  it("opens an Opt-in's Read more screen, and back returns", () => {
    const base = feedback();
    const added = addScreen(base, { title: "Terms" });
    const optIn = { type: "OptIn", name: "agree", label: "I agree", required: true };
    added.model.screens[0].blocks.push({ uid: "b-optin", component: optIn, inForm: true });
    const { model, uid: readMore } = addReadMore(added.model, "b-optin", { title: "Read more", text: "Terms" });
    const run = new PreviewRun(model);
    run.start();
    expect(run.progress.total).toBe(3);
    run.readMore("b-optin");
    expect(run.screen?.uid).toBe(readMore);
    run.back();
    expect(ids(run)).toBe("RECOMMEND");
    expect(run.canContinue).toBe(false);
    run.set("Choose_one", "0_Yes");
    run.set("agree", true);
    expect(run.canContinue).toBe(true);
  });
});
