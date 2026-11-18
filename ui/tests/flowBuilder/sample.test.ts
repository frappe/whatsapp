import { describe, expect, it } from "vitest";
import { parse, type FlowModel, type Screen } from "../../src/components/FlowBuilder/model";
import { sampleText, type Filled } from "../../src/components/FlowBuilder/preview/sample";
import { flowJson } from "./fixtures";

function screenById(model: FlowModel, id: string): Screen {
  return model.screens.find((screen) => screen.props.id === id)!;
}

function filled(form: Record<string, Record<string, unknown>>, data: Record<string, Record<string, unknown>> = {}): Filled {
  return {
    form: (uid) => form[uid] as never,
    data: (uid) => data[uid] as never,
  };
}

describe("sampleText", () => {
  const dealFeedback = parse(flowJson("ours", "deal_feedback"));
  const leadCapture = parse(flowJson("builder", "lead_capture"));
  const feedback = parse(flowJson("meta", "playground_feedback"));

  it("returns plain text as written, and nothing for a non-string", () => {
    const screen = dealFeedback.screens[0];
    expect(sampleText("Thanks for your time", dealFeedback, screen)).toBe("Thanks for your time");
    expect(sampleText(undefined, dealFeedback, screen)).toBe("");
    expect(sampleText(["a"], dealFeedback, screen)).toBe("");
  });

  it("shows a data reference as the screen's __example__", () => {
    const screen = dealFeedback.screens[0];
    expect(sampleText("Hi ${data.customer_name}", dealFeedback, screen)).toBe("Hi Asha");
  });

  it("resolves every reference in one text", () => {
    const prefilled = parse(flowJson("ours", "prefilled"));
    expect(sampleText("Hi ${data.first_name} ${data.last_name}", prefilled, prefilled.screens[0])).toBe("Hi Asha Rao");
  });

  it("prints a non-string example as text", () => {
    const prefilled = parse(flowJson("ours", "prefilled"));
    const screen = prefilled.screens[0];
    const key = Object.entries(screen.props.data as Record<string, { __example__: unknown }>).find(
      ([, value]) => typeof value.__example__ === "number"
    )![0];
    expect(sampleText(`\${data.${key}}`, prefilled, screen)).toBe("1");
  });

  it("prefers data passed into the screen over the example", () => {
    const screen = dealFeedback.screens[0];
    const passed = filled({}, { [screen.uid]: { customer_name: "Ravi" } });
    expect(sampleText("Hi ${data.customer_name}", dealFeedback, screen, passed)).toBe("Hi Ravi");
  });

  it("shows an unfilled form reference as the question's label, and a filled one as its value", () => {
    const screen = screenById(leadCapture, "YOUR_DETAILS");
    expect(sampleText("Sent to ${form.email}", leadCapture, screen)).toBe("Sent to [Email]");
    const typed = filled({ [screen.uid]: { email: "asha@example.com" } });
    expect(sampleText("Sent to ${form.email}", leadCapture, screen, typed)).toBe("Sent to asha@example.com");
  });

  it("resolves a form reference on another screen", () => {
    const budget = screenById(leadCapture, "BUDGET");
    const details = screenById(leadCapture, "YOUR_DETAILS");
    const text = "Thanks, ${screen.YOUR_DETAILS.form.full_name}";
    expect(sampleText(text, leadCapture, budget)).toBe("Thanks, [Full name]");
    expect(sampleText(text, leadCapture, budget, filled({ [details.uid]: { full_name: "Asha" } }))).toBe("Thanks, Asha");
  });

  it("shows a chosen option by its title, not its id", () => {
    const screen = feedback.screens[0];
    const chosen = filled({ [screen.uid]: { Choose_one: "0_Yes" } });
    expect(sampleText("You said ${form.Choose_one}", feedback, screen, chosen)).toBe("You said Yes");
  });

  it("names a reference it cannot resolve by its key", () => {
    const screen = feedback.screens[0];
    expect(sampleText("${data.nope}", feedback, screen)).toBe("[nope]");
  });

  it("reads a backtick expression as its text", () => {
    const screen = dealFeedback.screens[0];
    expect(sampleText("`${data.customer_name} - ${data.product}`", dealFeedback, screen)).toBe("Asha - CRM Pro");
  });
});
