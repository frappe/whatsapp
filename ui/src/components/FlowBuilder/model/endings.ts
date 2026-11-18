import { isQuestion } from "./catalogue";
import type { FlowModel, JsonObject, Screen } from "./types";

/** A screen whose footer finishes the form. */
export function isEnding(screen: Screen): boolean {
  return footerAction(screen)?.name === "complete";
}

/** The screen id the footer goes to, or undefined when it does not navigate. */
export function footerTarget(screen: Screen): string | undefined {
  const action = footerAction(screen);
  if (action?.name !== "navigate") return undefined;
  return String((action.next as JsonObject | undefined)?.name ?? "");
}

/**
 * The `complete` payload the builder writes for an ending: every question on the screens whose
 * footers lead into it, in path order, as `${screen.<id>.form.<name>}` (`${form.<name>}` on the
 * ending itself). The first question with a key wins.
 */
export function endingAnswers(model: FlowModel, endingUid: string): JsonObject {
  const answers: JsonObject = {};
  for (const screen of screensInto(model, endingUid)) {
    for (const block of screen.blocks.filter(isQuestion)) {
      const name = String(block.component.name ?? "");
      if (!name || name in answers) continue;
      answers[name] =
        screen.uid === endingUid ? `\${form.${name}}` : `\${screen.${screen.props.id}.form.${name}}`;
    }
  }
  return answers;
}

/** The screens on the footer paths into a screen, the screen included, in the order a contact meets them. */
export function screensInto(model: FlowModel, uid: string): Screen[] {
  const graph = new FooterGraph(model);
  const into = graph.ancestors(uid);
  const ordered: Screen[] = [];
  const visit = (screen: Screen) => {
    if (ordered.includes(screen) || !into.has(screen)) return;
    ordered.push(screen);
    const next = graph.next(screen);
    if (next) visit(next);
  };
  graph.entries().forEach(visit);
  model.screens.forEach(visit);
  return ordered;
}

class FooterGraph {
  private byId = new Map<string, Screen>();

  constructor(private model: FlowModel) {
    for (const screen of [...model.screens].reverse()) this.byId.set(String(screen.props.id), screen);
  }

  next(screen: Screen): Screen | undefined {
    const target = footerTarget(screen);
    return target === undefined ? undefined : this.byId.get(target);
  }

  entries(): Screen[] {
    const targets = new Set(this.model.screens.map((screen) => this.next(screen)));
    return this.model.screens.filter((screen) => !targets.has(screen));
  }

  ancestors(uid: string): Set<Screen> {
    const found = new Set(this.model.screens.filter((screen) => screen.uid === uid));
    let grew = true;
    while (grew) {
      grew = false;
      for (const screen of this.model.screens) {
        const next = this.next(screen);
        if (next && found.has(next) && !found.has(screen)) {
          found.add(screen);
          grew = true;
        }
      }
    }
    return found;
  }
}

function footerAction(screen: Screen): JsonObject | undefined {
  return screen.footer?.component["on-click-action"] as JsonObject | undefined;
}
