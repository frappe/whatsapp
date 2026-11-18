import { describe, expect, it } from "vitest";
import {
  addBlock,
  addScreen,
  createFlow,
  deleteBlock,
  endingAnswers,
  moveScreen,
  parse,
  renameAnswerKey,
  serialize,
  setFooter,
  type FlowModel,
} from "../../src/components/FlowBuilder/model";
import { flowJson } from "./fixtures";

/** Screens A, B and C, each with one question named after it, every footer finishing. */
function threeScreens(): FlowModel {
  let model = createFlow("A");
  model = addScreen(model, { title: "B" }).model;
  model = addScreen(model, { title: "C" }).model;
  for (const screen of model.screens) {
    model = addBlock(model, screen.uid, "TextInput", {
      text: String(screen.props.title).toLowerCase(),
    }).model;
  }
  return model;
}

const goTo = (model: FlowModel, from: number, to: string) =>
  setFooter(model, model.screens[from].uid, { action: { navigate: to } });

function findFooter(children: any[]): any {
  for (const child of children) {
    if (child.type === "Footer") return child;
    if (child.type === "Form") return findFooter(child.children);
  }
}

const footerAction = (model: FlowModel, screen: number) =>
  findFooter((serialize(model).screens as any[])[screen].layout.children)["on-click-action"];

const payload = (model: FlowModel, screen: number) => footerAction(model, screen).payload;

describe("ending answers", () => {
  it("are every question on the path into the ending, as global references", () => {
    let model = threeScreens();
    model = goTo(goTo(model, 0, "B"), 1, "C");

    expect(payload(model, 2)).toEqual({
      a: "${screen.A.form.a}",
      b: "${screen.B.form.b}",
      c: "${form.c}",
    });
  });

  it("follow the order a contact meets the screens, not the list order", () => {
    let model = threeScreens();
    model = goTo(goTo(model, 2, "B"), 1, "A");

    expect(Object.keys(payload(model, 0))).toEqual(["c", "b", "a"]);
    expect(Object.keys(payload(moveScreen(model, model.screens[1].uid, 0), 1))).toEqual(["c", "b", "a"]);
  });

  it("belong to each ending separately, and merge paths that join", () => {
    let model = threeScreens();
    model = goTo(model, 0, "B");

    expect(payload(model, 1)).toEqual({ a: "${screen.A.form.a}", b: "${form.b}" });
    expect(payload(model, 2)).toEqual({ c: "${form.c}" });

    model = goTo(goTo(threeScreens(), 0, "C"), 1, "C");
    expect(payload(model, 2)).toEqual({ a: "${screen.A.form.a}", b: "${screen.B.form.b}", c: "${form.c}" });
  });

  it("follow questions as they are added, renamed and deleted", () => {
    let model = goTo(threeScreens(), 0, "B");
    model = addBlock(model, model.screens[0].uid, "Dropdown", { text: "Size" }).model;
    model = renameAnswerKey(model, model.screens[1].blocks[0].uid, "bee");
    model = deleteBlock(model, model.screens[0].blocks[0].uid);

    expect(payload(model, 1)).toEqual({ size: "${screen.A.form.size}", bee: "${form.bee}" });
  });

  it("leave out text blocks, Advanced blocks and the first of two equal keys wins", () => {
    const model = parse(flowJson("ours", "lead_qualification"));
    const notInterested = model.screens[2].uid;

    expect(endingAnswers(model, notInterested)).toEqual({ reason: "${form.reason}" });
  });

  it("keep Custom answers as written whatever changes", () => {
    const model = parse(flowJson("meta", "agent_connect"));
    const written = payload(model, 0);
    const changed = addBlock(model, model.screens[0].uid, "TextInput", { text: "Phone" }).model;

    expect(changed.screens[0].footer?.customAnswers).toBe(true);
    expect(payload(changed, 0)).toEqual(written);
  });

  it("are left alone on a screen that does not finish", () => {
    const model = goTo(threeScreens(), 0, "B");

    expect(footerAction(model, 0)).toEqual({
      name: "navigate",
      next: { type: "screen", name: "B" },
      payload: {},
    });
  });
});

describe("a builder-made Flow parses back the same", () => {
  it("with generated answers, so editing it again keeps generating them", () => {
    let model = goTo(threeScreens(), 0, "B");
    const reparsed = parse(serialize(model));

    expect(reparsed.screens.map((screen) => screen.footer?.customAnswers)).toEqual([false, false, false]);
    model = addBlock(reparsed, reparsed.screens[0].uid, "TextArea", { text: "Notes" }).model;
    expect(payload(model, 1)).toEqual({
      a: "${screen.A.form.a}",
      notes: "${screen.A.form.notes}",
      b: "${form.b}",
    });
  });
});
