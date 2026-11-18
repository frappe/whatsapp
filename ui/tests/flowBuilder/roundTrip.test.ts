import { describe, expect, it } from "vitest";
import { parse, serialize } from "../../src/components/FlowBuilder/model";
import { flowJson, flowJsonNames } from "./fixtures";

describe("an unedited Flow serializes to exactly what was parsed", () => {
  for (const group of ["meta", "ours"] as const) {
    for (const name of flowJsonNames(group)) {
      it(`${group}/${name}`, () => {
        const json = flowJson(group, name);

        expect(JSON.stringify(serialize(parse(json)))).toBe(JSON.stringify(json));
      });
    }
  }
});
