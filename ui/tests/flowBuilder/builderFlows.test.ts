import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  addBlock,
  addScreen,
  createFlow,
  parse,
  problems,
  renameAnswerKey,
  serialize,
  setFooter,
  setPrefill,
  setSensitive,
  updateBlock,
  type FlowModel,
} from "../../src/components/FlowBuilder/model";
import { FLOW_JSON_DIR, flowJson } from "./fixtures";

/**
 * Flows made with the builder's operations. The JSON files are what the Python test runs the
 * Flow outline on; set WRITE_FLOW_FIXTURES=1 to rewrite them after a deliberate change.
 */
const BUILT: Record<string, () => FlowModel> = {
  blank: () => createFlow(),

  lead_capture() {
    let model = createFlow("Your details");
    model = addBlock(model, "s1", "TextHeading", { text: "Tell us about you" }).model;
    const name = addBlock(model, "s1", "TextInput", { text: "Full name" });
    model = setPrefill(name.model, name.uid, { example: "Asha" });
    const email = addBlock(model, "s1", "TextInput", { text: "Email" });
    model = updateBlock(email.model, email.uid, { "input-type": "email", required: true });
    const budget = addScreen(model, { title: "Budget" });
    model = setFooter(budget.model, "s1", { action: { navigate: "BUDGET" } });
    model = addBlock(model, budget.uid, "Dropdown", { text: "Budget" }).model;
    const notes = addBlock(model, budget.uid, "TextArea", { text: "Anything else?" });
    model = setSensitive(notes.model, notes.uid, true);
    return setFooter(model, budget.uid, { label: "Submit" });
  },

  feedback() {
    let model = createFlow("Feedback");
    model = addBlock(model, "s1", "RadioButtonsGroup", { text: "How was it?" }).model;
    model = addBlock(model, "s1", "CheckboxGroup", { text: "What did you like?" }).model;
    model = addBlock(model, "s1", "DatePicker", { text: "Visit date" }).model;
    const pin = addBlock(model, "s1", "TextInput", { text: "Member PIN" });
    model = updateBlock(pin.model, pin.uid, { "input-type": "passcode" });
    model = addBlock(model, "s1", "OptIn", { text: "You may contact me" }).model;
    const consent = model.screens[0].blocks.at(-1)!.uid;
    return renameAnswerKey(model, consent, "consent");
  },

  survey_edited() {
    let model = parse(flowJson("meta", "survey"));
    const screen = model.screens[0];
    const added = addBlock(model, screen.uid, "TextInput", {
      text: "Your email",
      index: screen.blocks.length,
    });
    model = updateBlock(added.model, added.uid, { "input-type": "email" });
    for (const block of model.screens[0].blocks.filter(
      (each) => each.component.type === "RadioButtonsGroup"
    )) {
      const words = String(block.component.name).replaceAll("_", " ");
      model = updateBlock(model, block.uid, { label: words[0].toUpperCase() + words.slice(1) });
    }
    return model;
  },
};

describe("builder-made Flows", () => {
  for (const [name, build] of Object.entries(BUILT)) {
    it(`${name} has no problems and matches its stored JSON`, () => {
      const json = serialize(build());
      if (process.env.WRITE_FLOW_FIXTURES) {
        writeFileSync(
          join(FLOW_JSON_DIR, "builder", `${name}.json`),
          `${JSON.stringify(json, null, "\t")}\n`
        );
      }

      expect(problems(build())).toEqual([]);
      expect(json).toEqual(flowJson("builder", name));
      expect(JSON.stringify(serialize(parse(json)))).toBe(JSON.stringify(json));
    });
  }
});
