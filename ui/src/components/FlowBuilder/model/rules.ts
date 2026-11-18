import { prefillKey } from "./answers";
import { RESERVED_SCREEN_IDS, isQuestion } from "./catalogue";
import { objects } from "./edit";
import { readMoreParent } from "./journey";
import { limitProblems } from "./limits";
import { jsonPaths, screenItems } from "./serialize";
import type { Block, FlowModel, Footer, JsonObject, Problem, Screen, Severity } from "./types";

const ANSWER_KEY = /^[A-Za-z0-9_]+$/;

/** Everything the builder can tell is wrong before Meta sees the Flow. */
export function problems(model: FlowModel): Problem[] {
  return new Rules(model).run();
}

/** Builds a problem with its JSON path; `property` points inside the screen or block. */
export class Reporter {
  readonly found: Problem[] = [];
  private paths = new Map<string, string>();

  constructor(model: FlowModel) {
    for (const [path, location] of jsonPaths(model))
      this.paths.set(location.blockId ?? location.screenId, path);
  }

  add(
    severity: Severity,
    code: string,
    message: string,
    screen: Screen,
    item?: Block | Footer,
    property?: string
  ) {
    const base = this.paths.get(item?.uid ?? screen.uid);
    const path = base && property ? `${base}.${property}` : base;
    this.found.push({ severity, code, message, screenId: screen.uid, blockId: item?.uid, path });
  }
}

class Rules {
  private report: Reporter;
  private byId = new Map<string, Screen>();

  constructor(private model: FlowModel) {
    this.report = new Reporter(model);
    for (const screen of model.screens)
      if (!this.byId.has(this.id(screen))) this.byId.set(this.id(screen), screen);
  }

  run(): Problem[] {
    this.screenIds();
    this.titles();
    this.endings();
    this.reachability();
    this.backToFirst();
    this.targets();
    this.footers();
    this.answerKeys();
    this.prefills();
    this.versionFeatures();
    limitProblems(this.model, this.report);
    return this.report.found;
  }

  private screenIds() {
    const seen = new Set<string>();
    for (const screen of this.model.screens) {
      const id = this.id(screen);
      const name = this.name(screen);
      if (!id) this.report.add("error", "screen-id-missing", `${name} has no screen ID.`, screen);
      else if (seen.has(id)) this.error("screen-id-duplicate", `Two screens use the ID ${id}.`, screen, "id");
      else if (RESERVED_SCREEN_IDS.includes(id))
        this.error("screen-id-reserved", `WhatsApp reserves the screen ID ${id}.`, screen, "id");
      else if (!ANSWER_KEY.test(id)) {
        this.error(
          "screen-id-format",
          `Screen ID ${id} can use only letters, numbers and underscores.`,
          screen,
          "id"
        );
      }
      seen.add(id);
    }
  }

  private titles() {
    for (const screen of this.model.screens) {
      const title = screen.props.title;
      if (typeof title !== "string" || !title.trim())
        this.error("empty-title", `${this.name(screen)} has no title.`, screen, "title");
    }
  }

  private endings() {
    const finishes = this.model.screens.some((screen) =>
      this.actions(screen).some(({ action }) => action.name === "complete")
    );
    if (!finishes && this.model.screens.length) {
      this.report.add(
        "error",
        "no-ending",
        'The form never finishes. Set a screen\'s button to "Finish the form".',
        this.model.screens[0]
      );
    }
  }

  private reachability() {
    const reached = new Set<Screen>();
    const visit = (screen: Screen | undefined) => {
      if (!screen || reached.has(screen)) return;
      reached.add(screen);
      for (const target of this.targetsOf(screen)) visit(this.byId.get(target));
    };
    visit(this.model.screens[0]);
    for (const screen of this.model.screens) {
      if (!reached.has(screen))
        this.report.add("warning", "unreachable-screen", `Nothing leads to ${this.name(screen)}.`, screen);
    }
  }

  /** Our outline takes the screens nothing navigates to as entry screens, so the first one would drop out. */
  private backToFirst() {
    const first = this.model.screens[0];
    if (!first) return;
    for (const screen of this.model.screens) {
      for (const { item, action } of this.actions(screen)) {
        if (action.name !== "navigate" || (action.next as JsonObject | undefined)?.name !== this.id(first))
          continue;
        this.report.add(
          "warning",
          "navigates-to-first-screen",
          `The button goes back to the first screen, ${this.name(first)}. Templates then can't prefill this Flow.`,
          screen,
          item
        );
      }
    }
  }

  private targets() {
    for (const screen of this.model.screens) {
      for (const { item, action } of this.actions(screen)) {
        const target = String((action.next as JsonObject | undefined)?.name ?? "");
        if (action.name !== "navigate" || this.byId.has(target)) continue;
        this.report.add(
          "error",
          "missing-target",
          `The button goes to a screen that doesn't exist: ${target || "none"}.`,
          screen,
          item
        );
      }
    }
  }

  private footers() {
    for (const screen of this.model.screens) {
      const components = screenItems(screen).flatMap((item) => [...objects(item.component)]);
      if (components.some((component) => component.type === "Footer" || component.type === "NavigationList"))
        continue;
      if (readMoreParent(this.model, screen.uid)) continue;
      this.report.add("error", "no-footer", `${this.name(screen)} has no button to continue.`, screen);
    }
  }

  private answerKeys() {
    const seen = new Set<string>();
    for (const screen of this.model.screens) {
      for (const block of screen.blocks.filter(isQuestion)) {
        const key = String(block.component.name ?? "");
        if (!ANSWER_KEY.test(key)) {
          this.report.add(
            "error",
            "invalid-key",
            `Answer key "${key}" can use only letters, numbers and underscores.`,
            screen,
            block,
            "name"
          );
        } else if (seen.has(key)) {
          this.report.add(
            "error",
            "duplicate-answer-key",
            `Two questions use the answer key "${key}".`,
            screen,
            block,
            "name"
          );
        }
        seen.add(key);
      }
    }
  }

  /** Data a navigation passes in is not a prefill: only the entry screen gets the template's data. */
  private prefills() {
    for (const screen of this.model.screens.slice(1)) {
      const passed = this.passedData(screen);
      for (const block of screen.blocks.filter(isQuestion)) {
        const key = prefillKey(screen, block);
        if (!key || passed.has(key)) continue;
        this.report.add(
          "warning",
          "prefill-outside-entry",
          "Only questions on the first screen can be prefilled from the template.",
          screen,
          block
        );
      }
    }
  }

  private versionFeatures() {
    const version = String(this.model.flow.version ?? "");
    const needs = (
      feature: string,
      minimum: string,
      screen: Screen,
      item?: Block | Footer,
      property?: string
    ) => {
      if (!isOlder(version, minimum)) return;
      const message = `${feature} needs Flow JSON ${minimum} or later. This Flow uses ${version}.`;
      this.report.add("error", "version-too-old", message, screen, item, property);
    };
    for (const screen of this.model.screens) {
      const sensitive = screen.props.sensitive;
      if (Array.isArray(sensitive) && sensitive.length)
        needs("Hiding answers in chat", "5.1", screen, undefined, "sensitive");
      for (const item of screenItems(screen)) {
        if (JSON.stringify(item.component).includes("${screen."))
          needs("Answers from other screens", "4.0", screen, item);
        if (item.component["init-value"] !== undefined)
          needs("A start value outside a Form", "4.0", screen, item, "init-value");
      }
    }
  }

  private passedData(screen: Screen): Set<string> {
    const keys = new Set<string>();
    for (const each of this.model.screens) {
      for (const { action } of this.actions(each)) {
        if (action.name === "navigate" && (action.next as JsonObject | undefined)?.name === this.id(screen)) {
          Object.keys((action.payload as JsonObject | undefined) ?? {}).forEach((key) => keys.add(key));
        }
      }
    }
    return keys;
  }

  private targetsOf(screen: Screen): string[] {
    const routes = (this.model.flow.routing_model as JsonObject | undefined)?.[this.id(screen)];
    const navigations = this.actions(screen)
      .filter(({ action }) => action.name === "navigate")
      .map(({ action }) => String((action.next as JsonObject | undefined)?.name ?? ""));
    return [...navigations, ...(Array.isArray(routes) ? routes.map(String) : [])];
  }

  private actions(screen: Screen): { item: Block | Footer; action: JsonObject }[] {
    return screenItems(screen).flatMap((item) =>
      [...objects(item.component)].flatMap((object) =>
        Object.entries(object)
          .filter(([key, value]) => key.endsWith("-action") && value && typeof value === "object")
          .map(([, action]) => ({ item, action: action as JsonObject }))
      )
    );
  }

  private error(code: string, message: string, screen: Screen, property: string) {
    this.report.add("error", code, message, screen, undefined, property);
  }

  private id(screen: Screen): string {
    return typeof screen.props.id === "string" ? screen.props.id : "";
  }

  private name(screen: Screen): string {
    const title = screen.props.title;
    return typeof title === "string" && title.trim()
      ? `"${title}"`
      : `Screen ${this.model.screens.indexOf(screen) + 1}`;
  }
}

function isOlder(version: string, minimum: string): boolean {
  const [major, minor] = version.split(".").map(Number);
  const [needMajor, needMinor] = minimum.split(".").map(Number);
  if (Number.isNaN(major)) return false;
  return major < needMajor || (major === needMajor && (minor || 0) < needMinor);
}
