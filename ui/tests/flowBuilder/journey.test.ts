import { describe, expect, it } from "vitest";
import {
  addBlock,
  addReadMore,
  addScreenInJourney,
  createFlow,
  deleteScreenInJourney,
  footerTarget,
  followsListOrder,
  isAdvanced,
  isEnding,
  journeyScreens,
  moveScreenInJourney,
  parse,
  problems,
  readMoreOf,
  removeReadMore,
  restoreScreens,
  serialize,
  setFooter,
  type FlowModel,
} from "../../src/components/FlowBuilder/model";
import { flowJson } from "./fixtures";

const ids = (model: FlowModel) => model.screens.map((screen) => screen.props.id);
const route = (model: FlowModel) =>
  journeyScreens(model).map((screen) => (isEnding(screen) ? "end" : footerTarget(screen)));

function threeScreens() {
  let model = createFlow("Your details");
  model = addScreenInJourney(model, { title: "Budget" }).model;
  model = addScreenInJourney(model, { title: "Thank you" }).model;
  return model;
}

describe("the journey follows the screens list", () => {
  it("sends each new screen's predecessor to it and ends on the last", () => {
    const model = threeScreens();

    expect(route(model)).toEqual(["BUDGET", "THANK_YOU", "end"]);
    expect(followsListOrder(model)).toBe(true);
  });

  it("rewires the buttons when a screen moves", () => {
    const model = moveScreenInJourney(threeScreens(), "s5", 0);

    expect(ids(model)).toEqual(["THANK_YOU", "YOUR_DETAILS", "BUDGET"]);
    expect(route(model)).toEqual(["YOUR_DETAILS", "BUDGET", "end"]);
  });

  it("rewires the buttons when a screen is deleted, and the undo puts it back", () => {
    const { model, removed } = deleteScreenInJourney(threeScreens(), "s3");

    expect(route(model)).toEqual(["THANK_YOU", "end"]);
    const restored = restoreScreens(model, removed);
    expect(ids(restored)).toEqual(["YOUR_DETAILS", "BUDGET", "THANK_YOU"]);
    expect(route(restored)).toEqual(["BUDGET", "THANK_YOU", "end"]);
  });

  it("writes the last screen's answers from every screen before it", () => {
    let model = createFlow("Your details");
    model = addBlock(model, "s1", "TextInput", { text: "Full name" }).model;
    model = addScreenInJourney(model, { title: "Thanks" }).model;

    const last = serialize(model).screens as { layout: { children: { [k: string]: unknown }[] } }[];
    expect(last[1].layout.children.at(-1)!["on-click-action"]).toEqual({
      name: "complete",
      payload: { full_name: "${screen.YOUR_DETAILS.form.full_name}" },
    });
  });

  it("reads Meta's default Feedback Flow as list order and keeps it as written", () => {
    const json = flowJson("meta", "playground_feedback");
    const model = parse(json);

    expect(followsListOrder(model)).toBe(true);
    expect(JSON.stringify(serialize(model))).toBe(JSON.stringify(json));
  });

  it("leaves a Flow whose navigation is not list order exactly as it was", () => {
    let model = threeScreens();
    model = setFooter(model, "s1", { action: { navigate: "THANK_YOU" } });
    expect(followsListOrder(model)).toBe(false);

    expect(route(model)).toEqual(["THANK_YOU", "THANK_YOU", "end"]);
    expect(route(moveScreenInJourney(model, "s5", 0))).toEqual(["end", "THANK_YOU", "THANK_YOU"]);
    const added = addScreenInJourney(model, { title: "Extra" }).model;
    expect(route(added)).toEqual(["THANK_YOU", "THANK_YOU", "end", "end"]);
  });

  it("does not take an ending in the middle as list order", () => {
    let model = threeScreens();
    model = setFooter(model, "s3", { action: "finish" });

    expect(followsListOrder(model)).toBe(false);
  });
});

describe("Read more screens", () => {
  function withOptIn() {
    let model = threeScreens();
    const optIn = addBlock(model, "s1", "OptIn", { text: "I agree to the terms" });
    return { model: optIn.model, optIn: optIn.uid };
  }

  it("adds a sub-screen the Opt-in opens, outside the journey", () => {
    const { model: withIt, optIn } = withOptIn();
    const { model, uid } = addReadMore(withIt, optIn, { title: "Read more", text: "Our terms" });

    expect(readMoreOf(model, optIn)?.uid).toBe(uid);
    expect(journeyScreens(model).map((screen) => screen.uid)).not.toContain(uid);
    expect(route(model)).toEqual(["BUDGET", "THANK_YOU", "end"]);
    const opt = model.screens[0].blocks[0];
    expect(isAdvanced(opt)).toBe(false);
    expect(opt.component["on-click-action"]).toEqual({
      name: "navigate",
      next: { type: "screen", name: model.screens.at(-1)!.props.id },
      payload: {},
    });
    expect(problems(model).filter((problem) => problem.severity === "error")).toEqual([]);
  });

  it("stays out of the journey when a screen is added or moved", () => {
    const { model: withIt, optIn } = withOptIn();
    let model = addReadMore(withIt, optIn, { title: "Read more", text: "Our terms" }).model;
    model = addScreenInJourney(model, { title: "Extra" }).model;
    model = moveScreenInJourney(model, "s1", 3);

    expect(journeyScreens(model).map((screen) => screen.props.title)).toEqual([
      "Budget",
      "Thank you",
      "Extra",
      "Your details",
    ]);
    expect(route(model)).toEqual(["THANK_YOU", "EXTRA", "YOUR_DETAILS", "end"]);
  });

  it("goes with its parent screen, and comes back with it", () => {
    const { model: withIt, optIn } = withOptIn();
    const model = addReadMore(withIt, optIn, { title: "Read more", text: "Our terms" }).model;
    const { model: without, removed } = deleteScreenInJourney(model, "s1");

    expect(without.screens.map((screen) => screen.props.title)).toEqual(["Budget", "Thank you"]);
    expect(readMoreOf(restoreScreens(without, removed), optIn)).toBeDefined();
  });

  it("removes the sub-screen and the Opt-in's link together", () => {
    const { model: withIt, optIn } = withOptIn();
    const model = removeReadMore(addReadMore(withIt, optIn, { title: "Read more", text: "x" }).model, optIn);

    expect(model.screens).toHaveLength(3);
    expect(model.screens[0].blocks[0].component["on-click-action"]).toBeUndefined();
  });
});
