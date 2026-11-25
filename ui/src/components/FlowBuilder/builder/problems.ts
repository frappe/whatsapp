import type { FlowModel, Problem, Severity } from "../model";
import type { FlowBuilderChrome } from "../chrome";

const EMPTY = ["empty-text", "empty-title"];

/** A row's warning icon: an error wins over a warning. `item` undefined is the Screen title row. */
export function rowSeverity(problems: Problem[], screen: string, item?: string): Severity | null {
  return worst(problems.filter((problem) => problem.screenId === screen && problem.blockId === item));
}

export function screenSeverity(problems: Problem[], screen: string): Severity | null {
  return worst(problems.filter((problem) => problem.screenId === screen));
}

/** The message under one field, e.g. the `label` of a block or `data-source[1].title`. */
export function fieldError(
  problems: Problem[],
  chrome: FlowBuilderChrome,
  { screen, item, property }: { screen: string; item?: string; property: string }
): string | undefined {
  const found = problems.find(
    (problem) =>
      problem.severity === "error" &&
      problem.screenId === screen &&
      problem.blockId === item &&
      problem.path?.endsWith(`.${property}`)
  );
  if (!found) return undefined;
  return EMPTY.includes(found.code) ? chrome.fieldEmpty : found.message;
}

/** The problem nearest the top of the builder: by screen, then Screen title, components, Button. */
export function firstProblem(model: FlowModel, problems: Problem[]): Problem | undefined {
  const place = (problem: Problem) => {
    const screenIndex = model.screens.findIndex((each) => each.uid === problem.screenId);
    const rows = model.screens[screenIndex]?.blocks.map((block) => block.uid) ?? [];
    const rowIndex = problem.blockId ? rows.indexOf(problem.blockId) : -1;
    const screen = screenIndex < 0 ? model.screens.length : screenIndex;
    const row = problem.blockId && rowIndex < 0 ? rows.length : rowIndex;
    return [screen, row];
  };
  return [...problems].sort((a, b) => {
    const [screenA, rowA] = place(a);
    const [screenB, rowB] = place(b);
    return screenA - screenB || rowA - rowB;
  })[0];
}

function worst(found: Problem[]): Severity | null {
  if (found.some((problem) => problem.severity === "error")) return "error";
  return found.length ? "warning" : null;
}
