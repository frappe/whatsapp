import { describe, expect, it } from "vitest";
import { isAdvanced, parse, serialize } from "../../src/components/FlowBuilder/model";
import { flowJson } from "./fixtures";

const types = (model: ReturnType<typeof parse>, screen: number) =>
  model.screens[screen].blocks.map((block) => [block.component.type, isAdvanced(block)]);

describe("parse", () => {
  it("lifts the blocks out of a Form and keeps the footer apart", () => {
    const model = parse(flowJson("ours", "deal_feedback"));

    expect(types(model, 1)).toEqual([
      ["RadioButtonsGroup", false],
      ["TextArea", false],
    ]);
    expect(model.screens[1].footer?.component.label).toBe("Next");
    expect(model.screens[1].form).toEqual({ type: "Form", name: "rate_form", children: null });
  });

  it("keeps logic, navigation lists and actions other than open_url as Advanced blocks", () => {
    expect(types(parse(flowJson("ours", "lead_qualification")), 0)).toEqual([
      ["RadioButtonsGroup", false],
      ["If", true],
    ]);
    expect(types(parse(flowJson("ours", "cyclic")), 1)).toEqual([["NavigationList", true]]);
    expect(types(parse(flowJson("ours", "customer_profile")), 1)).toEqual([
      ["PhotoPicker", false],
      ["OptIn", false],
      ["EmbeddedLink", true],
    ]);
  });

  it("gives every screen, block and footer its own id and never writes one", () => {
    const model = parse(flowJson("ours", "deal_feedback"));
    const uids = model.screens.flatMap((screen) => [
      screen.uid,
      screen.footer!.uid,
      ...screen.blocks.map((block) => block.uid),
    ]);

    expect(new Set(uids).size).toBe(uids.length);
    expect(JSON.stringify(serialize(model))).not.toMatch(/"uid"/);
  });

  it("generates an ending's answers when the payload is what the builder would write", () => {
    const survey = parse(flowJson("meta", "survey"));

    expect(survey.screens[0].footer?.customAnswers).toBe(false);
  });

  it("marks an ending whose payload differs as Custom answers", () => {
    const agent = parse(flowJson("meta", "agent_connect"));
    const deal = parse(flowJson("ours", "deal_feedback"));

    expect(agent.screens[0].footer?.customAnswers).toBe(true);
    expect(deal.screens[2].footer?.customAnswers).toBe(true);
  });

  it("keeps a screen without a usable layout as written", () => {
    const json = { version: "7.3", screens: [{ id: "A", layout: "broken" }] };

    expect(serialize(parse(json))).toEqual(json);
  });

  it("keeps a footer that is not last in its place", () => {
    const json = {
      version: "7.3",
      screens: [
        {
          id: "A",
          layout: {
            type: "SingleColumnLayout",
            children: [
              { type: "TextBody", text: "Before" },
              { type: "Footer", label: "Go", "on-click-action": { name: "complete", payload: {} } },
              { type: "TextBody", text: "After" },
            ],
          },
        },
      ],
    };

    expect(JSON.stringify(serialize(parse(json)))).toBe(JSON.stringify(json));
  });
});
