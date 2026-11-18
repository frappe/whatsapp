import { describe, expect, it } from "vitest";
import {
  addBlock,
  addOption,
  addScreen,
  changeTextType,
  createFlow,
  deleteBlock,
  moveBlock,
  moveOption,
  parse,
  removeOption,
  serialize,
  setFooter,
  setPrefill,
  setSensitive,
  updateBlock,
  updateOption,
  type FlowModel,
} from "../../src/components/FlowBuilder/model";
import { flowJson } from "./fixtures";

const components = (model: FlowModel, screen = 0) =>
  model.screens[screen].blocks.map((block) => block.component);

function twoScreens() {
  let model = createFlow();
  model = addScreen(model, { title: "Second" }).model;
  const name = addBlock(model, model.screens[0].uid, "TextInput", { text: "Full name" });
  const city = addBlock(name.model, model.screens[0].uid, "TextInput", { text: "City" });
  return { model: city.model, name: name.uid, city: city.uid };
}

describe("blocks", () => {
  it("adds a question whose answer key comes from its text and is unique in the Flow", () => {
    let model = addScreen(createFlow(), { title: "Second" }).model;
    model = addBlock(model, model.screens[0].uid, "TextInput", { text: "Full name" }).model;
    model = addBlock(model, model.screens[1].uid, "TextArea", { text: "Full name?" }).model;

    expect(components(model, 0)).toEqual([{ type: "TextInput", name: "full_name", label: "Full name" }]);
    expect(components(model, 1)).toEqual([{ type: "TextArea", name: "full_name_2", label: "Full name?" }]);
  });

  it("adds text and choice blocks with their defaults, at an index", () => {
    let model = createFlow();
    const uid = model.screens[0].uid;
    model = addBlock(model, uid, "Dropdown", { text: "Pick one" }).model;
    model = addBlock(model, uid, "TextHeading", { text: "Hello", index: 0 }).model;

    expect(components(model)).toEqual([
      { type: "TextHeading", text: "Hello" },
      {
        type: "Dropdown",
        name: "pick_one",
        label: "Pick one",
        "data-source": [
          { id: "option_1", title: "Option 1" },
          { id: "option_2", title: "Option 2" },
        ],
      },
    ]);
  });

  it("puts a new block of a Form screen inside the Form", () => {
    const model = parse(flowJson("ours", "deal_feedback"));
    const added = addBlock(model, model.screens[1].uid, "TextInput", { text: "Email", index: 2 }).model;

    expect(serialize(added).screens).toMatchObject([
      {},
      { layout: { children: [{ type: "Form", children: [{}, {}, { name: "email" }, { type: "Footer" }] }] } },
      {},
    ]);
  });

  it("updates a block's properties and removes the ones set to undefined", () => {
    const { model, name } = twoScreens();
    const updated = updateBlock(model, name, { label: "Name", required: true, "helper-text": "As on ID" });

    expect(components(updateBlock(updated, name, { "helper-text": undefined }))[0]).toEqual({
      type: "TextInput",
      name: "full_name",
      label: "Name",
      required: true,
    });
  });

  it("refuses to edit an Advanced block, or a type or answer key through an update", () => {
    const model = parse(flowJson("ours", "lead_qualification"));
    const advanced = model.screens[0].blocks[1].uid;
    const question = model.screens[0].blocks[0].uid;

    expect(() => updateBlock(model, advanced, { condition: "true" })).toThrow();
    expect(() => updateBlock(model, question, { type: "TextArea" })).toThrow();
    expect(() => updateBlock(model, question, { name: "other" })).toThrow();
  });

  it("moves a block within a screen", () => {
    const { model, city } = twoScreens();

    expect(components(moveBlock(model, city, model.screens[0].uid, 0)).map((c) => c.name)).toEqual([
      "city",
      "full_name",
    ]);
  });

  it("moves a block to another screen with its sensitive mark, and the ending's answers follow", () => {
    let { model, city } = twoScreens();
    model = setFooterTo(model, "SECOND");
    model = markSensitive(model, city);
    model = moveBlock(model, city, model.screens[1].uid, 0);

    const [first, second] = serialize(model).screens as Record<string, unknown>[];
    expect(first).not.toHaveProperty("sensitive");
    expect(second).toMatchObject({
      sensitive: ["city"],
      layout: {
        children: [
          { name: "city" },
          {
            "on-click-action": {
              payload: { full_name: "${screen.WELCOME.form.full_name}", city: "${form.city}" },
            },
          },
        ],
      },
    });
  });

  it("moves an Advanced block", () => {
    const model = parse(flowJson("ours", "lead_qualification"));
    const moved = moveBlock(model, model.screens[0].blocks[1].uid, model.screens[0].uid, 0);

    expect(components(moved).map((c) => c.type)).toEqual(["If", "RadioButtonsGroup"]);
  });

  it("deletes a block with its sensitive mark and its prefill declaration", () => {
    let { model, name } = twoScreens();
    model = markSensitive(model, name);
    model = prefill(model, name);
    model = deleteBlock(model, name);

    const screen = serialize(model).screens[0] as Record<string, unknown>;
    expect(screen).not.toHaveProperty("sensitive");
    expect(screen).not.toHaveProperty("data");
    expect(components(model).map((c) => c.name)).toEqual(["city"]);
  });
});

describe("choice options", () => {
  const dropdown = () => {
    const added = addBlock(createFlow(), "s1", "RadioButtonsGroup", { text: "Size" });
    return { model: added.model, uid: added.uid };
  };
  const options = (model: FlowModel) => components(model)[0]["data-source"];

  it("adds an option with a unique id from its title", () => {
    const { model, uid } = dropdown();
    const added = addOption(addOption(model, uid, { title: "Large" }), uid, {
      title: "Large",
      description: "XL",
    });

    expect(options(added)).toEqual([
      { id: "option_1", title: "Option 1" },
      { id: "option_2", title: "Option 2" },
      { id: "large", title: "Large" },
      { id: "large_2", title: "Large", description: "XL" },
    ]);
  });

  it("updates an option's title without changing its id, and reorders and removes options", () => {
    let { model, uid } = dropdown();
    model = updateOption(model, uid, 0, { title: "Small", description: "S" });
    model = moveOption(model, uid, 0, 1);
    model = removeOption(model, uid, 0);

    expect(options(model)).toEqual([{ id: "option_1", title: "Small", description: "S" }]);
  });
});

describe("text type", () => {
  it("converts a text block in place, keeping its text and position", () => {
    let model = addBlock(createFlow(), "s1", "TextBody", { text: "Hello" }).model;
    model = addBlock(model, "s1", "TextInput", { text: "Name" }).model;
    const uid = model.screens[0].blocks[0].uid;
    model = changeTextType(model, uid, "TextHeading");

    expect(components(model)[0]).toEqual({ type: "TextHeading", text: "Hello" });
    expect(model.screens[0].blocks[0].uid).toBe(uid);
    expect(() => changeTextType(model, model.screens[0].blocks[1].uid, "TextBody")).toThrow();
  });
});

function setFooterTo(model: FlowModel, id: string) {
  return setFooter(model, model.screens[0].uid, { action: { navigate: id } });
}

function markSensitive(model: FlowModel, uid: string) {
  return setSensitive(model, uid, true);
}

function prefill(model: FlowModel, uid: string) {
  return setPrefill(model, uid, { example: "Asha" });
}
