import { describe, expect, it } from "vitest";
import {
  addScreen,
  createFlow,
  deleteScreen,
  moveScreen,
  parse,
  renameScreen,
  serialize,
  setFooter,
  setScreenId,
} from "../../src/components/FlowBuilder/model";
import { flowJson } from "./fixtures";

const ids = (model: ReturnType<typeof parse>) => model.screens.map((screen) => screen.props.id);

describe("screens", () => {
  it("starts a blank Flow with one ending screen", () => {
    expect(serialize(createFlow())).toEqual({
      version: "7.3",
      screens: [
        {
          id: "WELCOME",
          title: "Welcome",
          terminal: true,
          layout: {
            type: "SingleColumnLayout",
            children: [
              { type: "Footer", label: "Continue", "on-click-action": { name: "complete", payload: {} } },
            ],
          },
        },
      ],
    });
  });

  it("adds a screen whose id comes from its title and is unique", () => {
    let model = createFlow();
    model = addScreen(model, { title: "Your details" }).model;
    model = addScreen(model, { title: "Your details!" }).model;
    model = addScreen(model, { title: "2 more" }).model;

    expect(ids(model)).toEqual(["WELCOME", "YOUR_DETAILS", "YOUR_DETAILS_B", "MORE"]);
  });

  it("adds a screen at an index", () => {
    const { model, uid } = addScreen(createFlow(), { title: "First", index: 0 });

    expect(model.screens[0].uid).toBe(uid);
  });

  it("never changes the model it was given", () => {
    const model = createFlow();
    const before = JSON.stringify(model);
    addScreen(model, { title: "Two" });
    renameScreen(model, model.screens[0].uid, "Hello");

    expect(JSON.stringify(model)).toBe(before);
  });

  it("renames a screen's title", () => {
    const model = createFlow();

    expect(renameScreen(model, model.screens[0].uid, "Hello").screens[0].props.title).toBe("Hello");
  });

  it("changes a screen id and every reference to it", () => {
    const model = parse(flowJson("ours", "lead_qualification"));
    const changed = serialize(setScreenId(model, model.screens[1].uid, "KEEN"));

    expect(JSON.stringify(changed)).not.toMatch(/"INTERESTED"/);
    expect(changed.screens).toMatchObject([
      { layout: { children: [{}, { then: [{ "on-click-action": { next: { name: "KEEN" } } }] }] } },
      { id: "KEEN" },
      {},
    ]);
  });

  it("changes routing model entries and global references with the id", () => {
    const routed = parse(flowJson("ours", "routed"));
    expect(serialize(setScreenId(routed, routed.screens[1].uid, "LAST")).routing_model).toEqual({
      START: ["LAST"],
      LAST: [],
    });

    const profile = parse(flowJson("ours", "customer_profile"));
    const changed = JSON.stringify(serialize(setScreenId(profile, profile.screens[0].uid, "PERSON")));
    expect(changed).toContain("${screen.PERSON.form.city}");
    expect(changed).not.toContain("${screen.CONTACT.");
  });

  it("reorders screens", () => {
    const model = parse(flowJson("ours", "deal_feedback"));

    expect(ids(moveScreen(model, model.screens[2].uid, 0))).toEqual(["DONE", "WELCOME", "RATE"]);
  });

  it("deletes a screen and leaves footers that went to it as they are", () => {
    const model = parse(flowJson("ours", "deal_feedback"));
    const deleted = deleteScreen(model, model.screens[2].uid);

    expect(ids(deleted)).toEqual(["WELCOME", "RATE"]);
    expect(serialize(deleted).screens).toMatchObject([
      {},
      { layout: { children: [{ children: [{}, {}, { "on-click-action": { next: { name: "DONE" } } }] }] } },
    ]);
  });
});

describe("footer", () => {
  it("goes to another screen, and no longer ends the form", () => {
    let model = createFlow();
    const next = addScreen(model, { title: "Thanks" });
    model = setFooter(next.model, model.screens[0].uid, { label: "Next", action: { navigate: "THANKS" } });

    expect(serialize(model).screens).toMatchObject([
      {
        id: "WELCOME",
        layout: {
          children: [
            {
              type: "Footer",
              label: "Next",
              "on-click-action": { name: "navigate", next: { type: "screen", name: "THANKS" }, payload: {} },
            },
          ],
        },
      },
      { id: "THANKS", terminal: true },
    ]);
    expect(serialize(model).screens[0]).not.toHaveProperty("terminal");
  });

  it("finishes the form, which makes the screen an ending with generated answers", () => {
    const model = parse(flowJson("meta", "agent_connect"));
    const finished = setFooter(model, model.screens[0].uid, { action: "finish" });

    expect(finished.screens[0].footer?.customAnswers).toBe(false);
    expect(serialize(finished).screens).toMatchObject([
      {
        terminal: true,
        layout: {
          children: [
            {
              children: [
                {},
                {},
                {},
                {},
                {},
                {
                  label: "Submit",
                  "on-click-action": {
                    name: "complete",
                    payload: {
                      first_name: "${form.first_name}",
                      second_name: "${form.second_name}",
                      services_interested: "${form.services_interested}",
                      additional_info: "${form.additional_info}",
                    },
                  },
                },
              ],
            },
          ],
        },
      },
    ]);
  });

  it("adds a footer to a screen that has none, inside its Form", () => {
    const json = {
      version: "7.3",
      screens: [
        {
          id: "A",
          layout: {
            type: "SingleColumnLayout",
            children: [{ type: "Form", name: "f", children: [{ type: "TextInput", name: "x", label: "X" }] }],
          },
        },
      ],
    };
    const model = parse(json);

    expect(
      serialize(setFooter(model, model.screens[0].uid, { label: "Done", action: "finish" })).screens
    ).toMatchObject([
      {
        terminal: true,
        layout: {
          children: [
            {
              type: "Form",
              children: [
                { name: "x" },
                { label: "Done", "on-click-action": { name: "complete", payload: { x: "${form.x}" } } },
              ],
            },
          ],
        },
      },
    ]);
  });
});
