import { describe, expect, it } from "vitest";
import {
  addBlock,
  addScreen,
  answerKey,
  clearPrefill,
  createFlow,
  moveBlock,
  parse,
  prefillKey,
  renameAnswerKey,
  serialize,
  setFooter,
  setPrefill,
  setSensitive,
  type FlowModel,
} from "../../src/components/FlowBuilder/model";
import { flowJson } from "./fixtures";

const screenJson = (model: FlowModel, index = 0) =>
  serialize(model).screens[index] as Record<string, unknown>;

function question(type = "TextInput", text = "Full name") {
  const added = addBlock(createFlow(), "s1", type, { text });
  return { model: added.model, uid: added.uid };
}

describe("answer keys", () => {
  it("come from the question text", () => {
    expect(answerKey("Full name")).toBe("full_name");
    expect(answerKey("  What's your e-mail?  ")).toBe("what_s_your_e_mail");
    expect(answerKey("Ünïcode only ✓")).toBe("n_code_only");
    expect(answerKey("???")).toBe("answer");
  });

  it("rename with the sensitive mark, the Form's start values and the references to it", () => {
    const model = parse(flowJson("ours", "customer_profile"));
    let renamed = setSensitive(model, model.screens[0].blocks[1].uid, true);
    renamed = renameAnswerKey(renamed, renamed.screens[0].blocks[1].uid, "town");

    const json = JSON.stringify(serialize(renamed));
    const contact = screenJson(renamed, 0) as {
      sensitive: string[];
      layout: { children: { name: string }[] };
    };
    expect(contact.sensitive).toEqual(["town"]);
    expect(contact.layout.children[1].name).toBe("town");
    expect(json).toContain('"city":"${screen.CONTACT.form.town}"');
    expect(json).not.toContain("form.city");
  });

  it("rename inside a Form moves its init-values entry", () => {
    const json = {
      version: "7.3",
      screens: [
        {
          id: "A",
          terminal: true,
          layout: {
            type: "SingleColumnLayout",
            children: [
              {
                type: "Form",
                name: "f",
                "init-values": { x: "hi" },
                children: [
                  { type: "TextInput", name: "x", label: "X" },
                  {
                    type: "Footer",
                    label: "Go",
                    "on-click-action": { name: "complete", payload: { x: "${form.x}" } },
                  },
                ],
              },
            ],
          },
        },
      ],
    };
    const model = parse(json);
    const renamed = renameAnswerKey(model, model.screens[0].blocks[0].uid, "y");

    expect(screenJson(renamed)).toMatchObject({
      layout: {
        children: [
          {
            "init-values": { y: "hi" },
            children: [{ name: "y" }, { "on-click-action": { payload: { y: "${form.y}" } } }],
          },
        ],
      },
    });
  });
});

describe("sensitive", () => {
  it("adds and removes the question from the screen's sensitive list", () => {
    const { model, uid } = question();
    const on = setSensitive(model, uid, true);

    expect(screenJson(on).sensitive).toEqual(["full_name"]);
    expect(screenJson(setSensitive(on, uid, false))).not.toHaveProperty("sensitive");
  });
});

describe("prefill from template", () => {
  it("declares the data key with an example and starts the question at it", () => {
    const { model, uid } = question();
    const prefilled = setPrefill(model, uid, { example: "Asha" });

    expect(screenJson(prefilled)).toMatchObject({
      data: { full_name: { type: "string", __example__: "Asha" } },
      layout: { children: [{ name: "full_name", "init-value": "${data.full_name}" }, {}] },
    });
    expect(prefillKey(prefilled.screens[0], prefilled.screens[0].blocks[0])).toBe("full_name");
  });

  it("declares the type the question answers with", () => {
    const cases: [string, Record<string, unknown>, unknown][] = [
      ["CheckboxGroup", { type: "array", items: { type: "string" } }, ["option_1"]],
      ["OptIn", { type: "boolean" }, true],
    ];
    for (const [type, declared, example] of cases) {
      const { model, uid } = question(type, "Pick");
      const data = screenJson(setPrefill(model, uid, { example: example as never })).data;
      expect(data).toEqual({ pick: { ...declared, __example__: example } });
    }
  });

  it("uses the Form's init-values inside a Form", () => {
    const form = parse(flowJson("meta", "agent_connect"));
    const prefilled = setPrefill(form, form.screens[0].blocks[0].uid, { key: "first", example: "Asha" });
    expect(screenJson(prefilled)).toMatchObject({
      data: { first: { type: "string", __example__: "Asha" } },
      layout: { children: [{ "init-values": { first_name: "${data.first}" } }] },
    });
    expect(JSON.stringify(screenJson(prefilled))).not.toContain('"init-value"');
  });

  it("is refused outside the first screen", () => {
    const { model } = question();
    const second = addScreen(model, { title: "Two" });
    const added = addBlock(second.model, second.uid, "TextInput", { text: "Email" });

    expect(() => setPrefill(added.model, added.uid, { example: "a@b.c" })).toThrow();
  });

  it("clears the start value, and the declaration once nothing else reads it", () => {
    let { model, uid } = question();
    model = setPrefill(model, uid, { example: "Asha" });
    model = addBlock(model, "s1", "TextHeading", { text: "Hi ${data.full_name}", index: 0 }).model;

    const kept = clearPrefill(model, uid);
    expect(screenJson(kept).data).toEqual({ full_name: { type: "string", __example__: "Asha" } });
    expect(kept.screens[0].blocks[1].component).not.toHaveProperty("init-value");

    const { model: alone, uid: only } = question();
    expect(screenJson(clearPrefill(setPrefill(alone, only, { example: "Asha" }), only))).not.toHaveProperty(
      "data"
    );
  });

  it("travels with a question moved to another screen, where the rules report it", () => {
    let { model, uid } = question();
    model = setPrefill(model, uid, { example: "Asha" });
    model = addScreen(model, { title: "Two" }).model;
    model = setFooter(model, "s1", { action: { navigate: "TWO" } });
    model = moveBlock(model, uid, model.screens[1].uid, 0);

    expect(screenJson(model, 0)).not.toHaveProperty("data");
    expect(screenJson(model, 1)).toMatchObject({
      data: { full_name: { type: "string", __example__: "Asha" } },
      layout: { children: [{ "init-value": "${data.full_name}" }, {}] },
    });
  });

  it("moves a Form question's start value out of the Form when it leaves it", () => {
    const json = {
      version: "7.3",
      screens: [
        {
          id: "A",
          layout: {
            type: "SingleColumnLayout",
            children: [
              { type: "TextBody", text: "Intro" },
              {
                type: "Form",
                name: "f",
                "init-values": { x: "hi" },
                children: [
                  { type: "TextInput", name: "x", label: "X" },
                  { type: "TextInput", name: "y", label: "Y" },
                ],
              },
              { type: "TextBody", text: "Outro" },
            ],
          },
        },
      ],
    };
    const model = parse(json);
    const moved = moveBlock(model, model.screens[0].blocks[1].uid, model.screens[0].uid, 0);

    expect(screenJson(moved)).toMatchObject({
      layout: {
        children: [
          { type: "TextInput", name: "x", "init-value": "hi" },
          { type: "TextBody" },
          { type: "Form", children: [{ name: "y" }] },
          { type: "TextBody" },
        ],
      },
    });
  });
});
