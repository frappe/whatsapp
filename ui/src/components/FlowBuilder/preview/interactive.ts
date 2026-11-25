import {
  footerAction,
  isQuestion,
  journeyScreens,
  navigateTarget,
  readMoreOf,
  type FlowModel,
  type Json,
  type JsonObject,
  type Screen,
} from "../model";
import { isReference, referenceValue, sampleText, type Filled, type Value } from "./sample";

/**
 * The phone in Interactive mode, as plain state: which screen shows, what was typed on each
 * screen and what each button passed on. The footer moves where its action says (the next
 * screen in list order for a builder-made Flow); `complete` ends in the "Sent" chat.
 */
export class PreviewRun {
  sent = false;
  private current: string | null = null;
  private trail: string[] = [];
  private forms: Record<string, Record<string, Value>> = {};
  private passed: Record<string, Record<string, Json>> = {};

  constructor(private model: FlowModel) {}

  get screen(): Screen | null {
    return this.screenAt(this.current) ?? null;
  }

  get progress(): { step: number; total: number } {
    const journey = journeyScreens(this.model);
    const onJourney = [this.current, ...[...this.trail].reverse()].find((uid) =>
      journey.some((screen) => screen.uid === uid)
    );
    return { step: journey.findIndex((screen) => screen.uid === onJourney) + 1, total: journey.length };
  }

  get canGoBack(): boolean {
    return this.trail.length > 0;
  }

  get canContinue(): boolean {
    return !!this.screen && this.missing().length === 0;
  }

  /** What `${…}` references read on the phone. */
  get filled(): Filled {
    return { form: (uid) => this.forms[uid], data: (uid) => this.passed[uid] };
  }

  /** The required questions on this screen that have no answer yet. */
  missing(): string[] {
    const screen = this.screen;
    if (!screen) return [];
    return questions(screen)
      .filter((component) => component.required === true && isEmpty(this.value(String(component.name))))
      .map((component) => String(component.name));
  }

  value(name: string): Value | undefined {
    return this.current ? this.forms[this.current]?.[name] : undefined;
  }

  set(name: string, value: Value) {
    if (!this.current) return;
    this.forms[this.current] = { ...this.forms[this.current], [name]: value };
  }

  start() {
    this.forms = {};
    this.passed = {};
    this.sent = false;
    this.trail = [];
    this.enter(journeyScreens(this.model)[0]?.uid ?? null);
  }

  restart() {
    this.start();
  }

  /** The static preview: any screen, with no way back. */
  show(uid: string | null) {
    this.sent = false;
    this.trail = [];
    this.enter(uid);
  }

  continue() {
    const screen = this.screen;
    if (!screen || !this.canContinue) return;
    const action = footerAction(screen);
    const next = this.nextScreen(screen, action);
    if (!next) {
      this.sent = true;
      return;
    }
    this.passed[next.uid] = { ...this.passed[next.uid], ...this.payload(action, screen) };
    this.trail.push(screen.uid);
    this.enter(next.uid);
  }

  back() {
    const previous = this.trail.pop();
    if (previous) this.enter(previous);
  }

  readMore(optInUid: string) {
    const screen = readMoreOf(this.model, optInUid);
    if (!screen || !this.current) return;
    this.trail.push(this.current);
    this.enter(screen.uid);
  }

  /** After an edit: keep the screen and the answers whose questions are still there. */
  sync(model: FlowModel) {
    this.model = model;
    for (const uid of Object.keys(this.forms)) {
      const screen = this.screenAt(uid);
      if (!screen) delete this.forms[uid];
      else this.forms[uid] = keep(this.forms[uid], questionNames(screen));
    }
    this.trail = this.trail.filter((uid) => this.screenAt(uid));
    if (this.screenAt(this.current)) this.enter(this.current);
    else this.show(journeyScreens(model)[0]?.uid ?? null);
  }

  private enter(uid: string | null) {
    this.current = uid;
    const screen = this.screenAt(uid);
    if (screen) this.seed(screen);
  }

  /** Questions start from their `init-value`, or the Form's `init-values`. */
  private seed(screen: Screen) {
    const formValues = (screen.form?.["init-values"] ?? {}) as JsonObject;
    const form = { ...this.forms[screen.uid] };
    for (const component of questions(screen)) {
      const name = String(component.name);
      const initial = component["init-value"] ?? formValues[name];
      if (form[name] !== undefined || initial === undefined) continue;
      const value = typeof initial === "string" ? this.read(initial, screen) : initial;
      if (isValue(value)) form[name] = value;
    }
    this.forms[screen.uid] = form;
  }

  private payload(action: JsonObject | undefined, screen: Screen): Record<string, Json> {
    const payload = (action?.payload ?? {}) as JsonObject;
    return Object.fromEntries(
      Object.entries(payload).map(([key, value]) => [
        key,
        typeof value === "string" ? this.read(value, screen) : value,
      ])
    );
  }

  /** A whole reference keeps its raw value (an option id stays an id); other text is filled in. */
  private read(text: string, screen: Screen): Json {
    if (!text.includes("${")) return text;
    if (!isReference(text)) return sampleText(text, this.model, screen, this.filled);
    return referenceValue(text, this.model, screen, this.filled) ?? "";
  }

  private nextScreen(screen: Screen, action: JsonObject | undefined): Screen | undefined {
    if (action?.name === "complete") return undefined;
    if (action?.name === "navigate") return this.target(action);
    return this.journeyAfter(screen);
  }

  private target(action: JsonObject): Screen | undefined {
    const id = navigateTarget(action);
    return this.model.screens.find((screen) => screen.props.id === id);
  }

  private journeyAfter(screen: Screen): Screen | undefined {
    const journey = journeyScreens(this.model);
    return journey[journey.findIndex((each) => each.uid === screen.uid) + 1];
  }

  private screenAt(uid: string | null): Screen | undefined {
    return uid ? this.model.screens.find((screen) => screen.uid === uid) : undefined;
  }
}

function questions(screen: Screen): JsonObject[] {
  return screen.blocks.filter(isQuestion).map((block) => block.component);
}

function questionNames(screen: Screen): Set<string> {
  return new Set(questions(screen).map((component) => String(component.name)));
}

function isEmpty(value: Value | undefined): boolean {
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "string") return !value.trim();
  return value !== true;
}

function isValue(value: Json): value is Value {
  if (typeof value === "string" || typeof value === "boolean") return true;
  return Array.isArray(value) && value.every((each) => typeof each === "string");
}

function keep(values: Record<string, Value>, names: Set<string>): Record<string, Value> {
  return Object.fromEntries(Object.entries(values).filter(([name]) => names.has(name)));
}
