import { describe, expect, it } from "vitest";
import { printJson } from "../../src/components/FlowBuilder/jsonText";
import { jsonPaths, parse, serialize } from "../../src/components/FlowBuilder/model";
import { flowJson, flowJsonNames } from "./fixtures";

describe("printJson", () => {
  it("prints what JSON.stringify prints", () => {
    for (const name of flowJsonNames("meta")) {
      const json = flowJson("meta", name);
      expect(printJson(json).text).toBe(JSON.stringify(json, null, 2));
    }
  });

  it("knows the line every screen and block starts on", () => {
    const model = parse(flowJson("builder", "lead_capture"));
    const { text, lines } = printJson(serialize(model));
    const rows = text.split("\n");

    for (const path of jsonPaths(model).keys()) {
      const row = rows[lines.get(path)! - 1];
      expect(row.trim()).toMatch(/^\{|^"/);
    }
    expect(rows[lines.get("screens[0].layout.children[1]")! - 1].trim()).toBe("{");
    expect(rows[lines.get("screens[0].layout.children[1]")!].trim()).toBe('"type": "TextInput",');
  });
});
