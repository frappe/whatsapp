import { describe, expect, it } from "vitest";
import { locate, metaProblems, parse } from "../../src/components/FlowBuilder/model";
import { flowJson } from "./fixtures";

/** The shape of `validation_errors[]` in `flows/meta_fixtures.validation_error`. */
function validationError(message: string, path: string) {
  return {
    error: "INVALID_PROPERTY_VALUE",
    error_type: "FLOW_JSON_ERROR",
    message,
    line_start: 12,
    line_end: 12,
    column_start: 4,
    column_end: 14,
    pointers: [{ line_start: 12, line_end: 12, column_start: 4, column_end: 14, path }],
  };
}

describe("Meta's validation errors", () => {
  const model = parse(flowJson("ours", "deal_feedback"));
  const [welcome, rate] = model.screens;

  it("point at the block their path is inside", () => {
    expect(locate(model, "screens[1].layout.children[0].children[1].label")).toEqual({
      screenId: rate.uid,
      blockId: rate.blocks[1].uid,
    });
    expect(locate(model, "screens[1].layout.children[0].children[2]")).toEqual({
      screenId: rate.uid,
      blockId: rate.footer!.uid,
    });
  });

  it("point at the screen when the path stops above its blocks", () => {
    expect(locate(model, "screens[0].layout")).toEqual({ screenId: welcome.uid });
    expect(locate(model, "screens[1].layout.children[0]")).toEqual({ screenId: rate.uid });
  });

  it("point nowhere when the path is outside every screen", () => {
    expect(locate(model, "routing_model")).toBeUndefined();
    expect(locate(model, "screens[9].layout")).toBeUndefined();
  });

  it("become problems in Meta's words", () => {
    const errors = [
      validationError("Invalid value for label.", "screens[1].layout.children[0].children[0].label"),
      { error: "INVALID_VERSION", error_type: "FLOW_JSON_ERROR", message: "Version 1.0 is not supported." },
    ];

    expect(metaProblems(model, errors)).toEqual([
      {
        severity: "error",
        code: "INVALID_PROPERTY_VALUE",
        message: "Invalid value for label.",
        screenId: rate.uid,
        blockId: rate.blocks[0].uid,
        path: "screens[1].layout.children[0].children[0].label",
      },
      { severity: "error", code: "INVALID_VERSION", message: "Version 1.0 is not supported.", screenId: "" },
    ]);
  });
});
