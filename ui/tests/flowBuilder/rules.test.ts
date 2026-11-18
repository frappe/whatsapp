import { describe, expect, it } from "vitest";
import {
  addBlock,
  addOption,
  addScreen,
  createFlow,
  deleteScreen,
  moveBlock,
  parse,
  problems,
  removeOption,
  setFooter,
  setPrefill,
  setScreenId,
  setSensitive,
  serialize,
  updateBlock,
  updateOption,
  type FlowModel,
  type JsonObject,
} from "../../src/components/FlowBuilder/model";
import { flowJson, flowJsonNames } from "./fixtures";

const codes = (model: FlowModel) => problems(model).map((problem) => problem.code);

function withQuestion(type = "TextInput", text = "Full name") {
  const added = addBlock(createFlow(), "s1", type, { text });
  return { model: added.model, uid: added.uid };
}

function screenJson(screens: JsonObject[]): FlowModel {
  return parse({ version: "7.3", screens });
}

describe("a clean Flow", () => {
  it("has no problems when the builder made it", () => {
    let model = withQuestion().model;
    model = addScreen(model, { title: "Thanks" }).model;
    model = setFooter(model, "s1", { action: { navigate: "THANKS" } });

    expect(problems(model)).toEqual([]);
  });

  it("has no problems for our valid fixtures", () => {
    expect(codes(parse(flowJson("ours", "deal_feedback")))).toEqual([]);
    expect(codes(parse(flowJson("ours", "lead_qualification")))).toEqual([]);
  });
});

describe("screen ids", () => {
  it("reports a missing, duplicate, reserved or malformed id", () => {
    let model = addScreen(addScreen(createFlow(), { title: "Two" }).model, { title: "Three" }).model;
    model = setFooter(setFooter(model, "s1", { action: { navigate: "TWO" } }), model.screens[1].uid, {
      action: { navigate: "THREE" },
    });

    expect(codes(setScreenId(model, model.screens[1].uid, ""))).toContain("screen-id-missing");
    expect(codes(setScreenId(model, model.screens[1].uid, "WELCOME"))).toContain("screen-id-duplicate");
    expect(codes(setScreenId(model, model.screens[1].uid, "SUCCESS"))).toContain("screen-id-reserved");
    expect(codes(setScreenId(model, model.screens[1].uid, "TWO-2"))).toContain("screen-id-format");
  });

  it("names the second screen of a duplicate pair", () => {
    const model = setScreenId(addScreen(createFlow(), { title: "Two" }).model, "s3", "WELCOME");
    const duplicate = problems(model).find((problem) => problem.code === "screen-id-duplicate");

    expect(duplicate).toMatchObject({ severity: "error", screenId: "s3", path: "screens[1].id" });
  });
});

describe("navigation", () => {
  it("reports a Flow that never finishes", () => {
    const model = setFooter(addScreen(createFlow(), { title: "Two" }).model, "s1", {
      action: { navigate: "TWO" },
    });
    const looping = setFooter(model, "s3", { action: { navigate: "WELCOME" } });

    expect(codes(looping)).toEqual(["no-ending", "navigates-to-first-screen"]);
  });

  it("counts an ending inside an Advanced block", () => {
    expect(codes(parse(flowJson("ours", "customer_profile")))).not.toContain("no-ending");
  });

  it("reports a screen nothing reaches as a warning", () => {
    const model = addScreen(createFlow(), { title: "Lost" }).model;

    expect(problems(model)).toMatchObject([
      { severity: "warning", code: "unreachable-screen", screenId: "s3" },
    ]);
  });

  it("counts navigation inside Advanced blocks and the routing model", () => {
    expect(codes(parse(flowJson("ours", "lead_qualification")))).not.toContain("unreachable-screen");
    expect(codes(parse(flowJson("ours", "routed")))).not.toContain("unreachable-screen");
  });

  it("reports navigation to a deleted screen on the button that goes there", () => {
    const model = parse(flowJson("ours", "deal_feedback"));
    const deleted = deleteScreen(model, model.screens[2].uid);
    const missing = problems(deleted).filter((problem) => problem.code === "missing-target");

    expect(missing).toMatchObject([
      {
        severity: "error",
        screenId: model.screens[1].uid,
        blockId: model.screens[1].footer!.uid,
        path: "screens[1].layout.children[0].children[2]",
      },
    ]);
    expect(missing[0].message).toContain("DONE");
  });

  it("reports navigation to a missing screen inside an Advanced block", () => {
    const model = parse(flowJson("ours", "lead_qualification"));
    const deleted = deleteScreen(model, model.screens[2].uid);

    expect(problems(deleted)).toContainEqual(
      expect.objectContaining({ code: "missing-target", blockId: model.screens[0].blocks[1].uid })
    );
  });

  it("warns on a button that goes back to the first screen, which then is no entry screen", () => {
    let model = addScreen(createFlow(), { title: "Details" }).model;
    model = addScreen(model, { title: "Thanks" }).model;
    const [first, second] = model.screens;
    model = setFooter(model, first.uid, { action: { navigate: "DETAILS" } });
    model = setFooter(model, second.uid, { action: { navigate: "WELCOME" } });

    expect(problems(model)).toEqual([
      expect.objectContaining({ code: "unreachable-screen" }),
      expect.objectContaining({
        severity: "warning",
        code: "navigates-to-first-screen",
        screenId: second.uid,
        blockId: second.footer!.uid,
      }),
    ]);
    expect(codes(setFooter(model, second.uid, { action: "finish" }))).not.toContain(
      "navigates-to-first-screen"
    );
  });

  it("reports a screen without a button, unless it uses a navigation list", () => {
    const model = screenJson([
      { id: "A", terminal: true, layout: { type: "SingleColumnLayout", children: [] } },
    ]);

    expect(codes(model)).toContain("no-footer");
    expect(codes(parse(flowJson("ours", "cyclic")))).not.toContain("no-footer");
  });
});

describe("questions", () => {
  it("reports a duplicate answer key on the later question", () => {
    const model = screenJson([
      {
        id: "A",
        terminal: true,
        layout: {
          type: "SingleColumnLayout",
          children: [
            { type: "TextInput", name: "name", label: "One" },
            { type: "TextInput", name: "name", label: "Two" },
            { type: "Footer", label: "Go", "on-click-action": { name: "complete", payload: {} } },
          ],
        },
      },
    ]);

    expect(problems(model).filter((problem) => problem.code === "duplicate-answer-key")).toMatchObject([
      { severity: "error", blockId: model.screens[0].blocks[1].uid },
    ]);
  });

  it("reports an answer key the outline can't read", () => {
    const json = screenJson([
      {
        id: "A",
        terminal: true,
        layout: {
          type: "SingleColumnLayout",
          children: [
            { type: "OptIn", name: "T&Cs", label: "I agree" },
            { type: "Footer", label: "Go", "on-click-action": { name: "complete", payload: {} } },
          ],
        },
      },
    ]);

    expect(codes(json)).toContain("invalid-key");
  });

  it("reports empty labels, texts, button labels and option titles", () => {
    let { model, uid } = withQuestion("Dropdown", "Size");
    model = updateBlock(model, uid, { label: " " });
    model = updateOption(model, uid, 0, { title: "" });
    model = addBlock(model, "s1", "TextBody", { text: "" }).model;
    model = setFooter(model, "s1", { label: "" });

    expect(codes(model).filter((code) => code === "empty-text")).toHaveLength(4);
  });

  it("reports an empty screen title and an Image with no file", () => {
    let model = addBlock(createFlow(" "), "s1", "Image").model;

    expect(problems(model).filter((problem) => problem.code === "empty-title")[0]?.path).toBe("screens[0].title");
    expect(codes(model)).toContain("empty-image");
    model = updateBlock(model, model.screens[0].blocks[0].uid, { src: "iVBORw0KGgo=" });
    expect(codes(model)).not.toContain("empty-image");
  });

  it("reports choice lists that are empty, too short or too long", () => {
    let { model, uid } = withQuestion("RadioButtonsGroup", "Size");
    model = removeOption(removeOption(model, uid, 0), uid, 0);
    expect(codes(model)).toContain("no-options");

    const chips = withQuestion("ChipsSelector", "Tags");
    expect(codes(removeOption(chips.model, chips.uid, 0))).toContain("too-few-options");

    for (let i = 0; i < 19; i++) model = addOption(model, uid, { title: `Size ${i}` });
    expect(codes(model)).not.toContain("too-many-options");
    model = addOption(model, uid, { title: "One more" });
    model = addOption(model, uid, { title: "And another" });
    expect(codes(model)).toContain("too-many-options");
  });

  it("allows a Dropdown 200 options without images, 100 with", () => {
    let { model, uid } = withQuestion("Dropdown", "Country");
    for (let i = 0; i < 148; i++) model = addOption(model, uid, { title: `C ${i}` });
    expect(codes(model)).not.toContain("too-many-options");

    model = updateOption(model, uid, 0, { image: "iVBORw0KGgo=" });
    expect(codes(model)).toContain("too-many-options");
  });
});

describe("Meta's limits", () => {
  it("reports texts over the documented limit with where they are", () => {
    let { model, uid } = withQuestion("TextInput", "A label of more than twenty");
    model = updateBlock(model, uid, { "helper-text": "x".repeat(81) });
    model = setFooter(model, "s1", { label: "y".repeat(36) });
    const long = problems(model).filter((problem) => problem.code === "text-too-long");

    expect(long.map((problem) => problem.path)).toEqual([
      "screens[0].layout.children[0].label",
      "screens[0].layout.children[0].helper-text",
      "screens[0].layout.children[1].label",
    ]);
    expect(long[0].message).toBe("Question is 27 characters long. WhatsApp allows 20.");
  });

  it("reports option texts over the limit", () => {
    const { model, uid } = withQuestion("RadioButtonsGroup", "Size");

    expect(codes(updateOption(model, uid, 0, { title: "t".repeat(31) }))).toContain("text-too-long");
  });

  it("reports more components of a kind than a screen may have", () => {
    let model = createFlow();
    for (let i = 0; i < 6; i++) model = addBlock(model, "s1", "OptIn", { text: `Agree ${i}` }).model;

    expect(codes(model)).toContain("too-many-on-screen");
  });
});

describe("prefill", () => {
  it("reports a prefilled question outside the first screen", () => {
    let { model, uid } = withQuestion();
    model = setPrefill(model, uid, { example: "Asha" });
    model = addScreen(model, { title: "Two" }).model;
    model = setFooter(model, "s1", { action: { navigate: "TWO" } });
    model = moveBlock(model, uid, model.screens[1].uid, 0);

    expect(problems(model)).toMatchObject([
      { code: "prefill-outside-entry", severity: "warning", blockId: uid },
    ]);
  });

  it("allows data that a navigation passes to a later screen", () => {
    expect(codes(parse(flowJson("ours", "deal_feedback")))).not.toContain("prefill-outside-entry");
  });
});

describe("Flow JSON version", () => {
  it("reports features the Flow's version does not have", () => {
    const survey = parse(flowJson("meta", "survey"));
    const question = survey.screens[0].blocks.find((block) => block.component.name === "source")!;
    const hidden = problems(setSensitive(survey, question.uid, true));

    expect(hidden).toContainEqual(
      expect.objectContaining({ code: "version-too-old", severity: "error", path: "screens[0].sensitive" })
    );
    expect(hidden.find((problem) => problem.code === "version-too-old")?.message).toBe(
      "Hiding answers in chat needs Flow JSON 5.1 or later. This Flow uses 3.1."
    );
  });

  it("reports answers taken from other screens before 4.0", () => {
    let model = addScreen(createFlow(), { title: "Two" }).model;
    model = addBlock(model, "s1", "TextInput", { text: "Name" }).model;
    model = setFooter(model, "s1", { action: { navigate: "TWO" } });
    const json = { ...serialize(model), version: "3.1" };

    expect(codes(parse(json))).toEqual(["version-too-old"]);
  });
});

describe("fixtures", () => {
  it("run without throwing on every stored Flow", () => {
    for (const group of ["meta", "ours"] as const) {
      for (const name of flowJsonNames(group))
        expect(() => problems(parse(flowJson(group, name)))).not.toThrow();
    }
  });
});
