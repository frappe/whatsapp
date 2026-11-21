import {
  createFlow,
  metaProblems,
  parse,
  problems,
  serialize,
  type FlowModel,
  type JsonObject,
  type Problem,
} from "./model";
import { readJson, type JsonError } from "./jsonText";
import type {
  BuilderFlow,
  FlowBuilderApi,
  FlowState,
  PreviewSettings,
  SaveState,
  Selection,
  TemplateRef,
} from "./types";

/** Meta does not allow edits once a Flow leaves Draft. */
export const EDITABLE_STATUS = "Draft";

export const AUTOSAVE_MS = 1500;

/**
 * One open Flow: the model, what was last saved, and Meta's answer to it. Plain TypeScript, so it
 * runs in tests; `useFlowBuilder` makes it reactive. Every edit replaces `model`, never changes it,
 * and is saved once the edits pause for `AUTOSAVE_MS`.
 */
export class BuilderSession {
  loading = false;
  loadError: unknown = null;
  flow: Omit<BuilderFlow, "flow_json"> | null = null;
  model: FlowModel | null = null;
  modified = "";
  dirty = false;
  saving = false;
  saveError: unknown = null;
  /** Someone saved the Flow after it was opened here (WhatsApp Manager, Desk, another tab). */
  conflict = false;
  localProblems: Problem[] = [];
  /** Meta's validation errors, located on the model that was uploaded. */
  metaFound: Problem[] = [];
  selection: Selection = { screen: null, block: null };
  preview: PreviewSettings = { interactive: false, theme: "light" };
  private savedJson = "";
  private timer: ReturnType<typeof setTimeout> | undefined;
  private running: Promise<void> | null = null;
  private again = false;

  constructor(
    private api: FlowBuilderApi,
    readonly name: string,
    /** The user's write permission on the Flow; without it every Flow opens read only. */
    readonly canWrite = true
  ) {}

  get readOnly(): boolean {
    return !this.canWrite || (!!this.flow && this.flow.status !== EDITABLE_STATUS);
  }

  get saveState(): SaveState {
    if (this.conflict) return "conflict";
    if (this.saveError) return "failed";
    return this.dirty || this.saving ? "saving" : "saved";
  }

  get problems(): Problem[] {
    const all = [...this.metaFound, ...this.localProblems];
    return [...all.filter((p) => p.severity === "error"), ...all.filter((p) => p.severity === "warning")];
  }

  get errorCount(): number {
    return this.problems.filter((problem) => problem.severity === "error").length;
  }

  get printed(): string | null {
    return this.model ? JSON.stringify(serialize(this.model), null, 2) : null;
  }

  async load() {
    clearTimeout(this.timer);
    this.loading = true;
    this.loadError = null;
    try {
      const { flow_json, ...flow } = await this.api.get(this.name);
      const model = flowJson(flow_json) ? parse(flowJson(flow_json)!) : createFlow();
      this.flow = flow;
      this.modified = flow.modified;
      this.conflict = false;
      this.saveError = null;
      this.metaFound = metaProblems(model, flow.validation_errors ?? []);
      this.setSaved(model);
      this.selection = { screen: model.screens[0]?.uid ?? null, block: null };
    } catch (e) {
      this.loadError = e;
    } finally {
      this.loading = false;
    }
  }

  apply(model: FlowModel) {
    if (this.readOnly) throw new Error(`A ${this.flow!.status} Flow can't be changed`);
    this.model = model;
    this.dirty = text(model) !== this.savedJson;
    this.keepSelection(model);
    this.scheduleSave();
  }

  checkRules() {
    this.localProblems = this.model ? problems(this.model) : [];
  }

  /** Saves now. Asked while a save runs, it saves once more after it. */
  save(): Promise<void> {
    clearTimeout(this.timer);
    if (this.running) {
      this.again = true;
      return this.running;
    }
    if (!this.canSave) return Promise.resolve();
    this.running = this.saveUntilDone().finally(() => (this.running = null));
    return this.running;
  }

  /** Saves what is pending now; true once everything is saved. */
  async flush(): Promise<boolean> {
    await this.save();
    return !this.dirty;
  }

  dispose() {
    clearTimeout(this.timer);
  }

  /** Throws Meta's refusal, so the confirm dialog can show it. */
  async publish() {
    const state = await this.api.publish(this.name);
    this.takeState(state, this.model!);
  }

  copy(flowName: string): Promise<string> {
    return this.api.copy(this.name, flowName);
  }

  /** The JSON tab's text, or where it is broken. A broken text changes nothing. */
  applyJson(json: string): JsonError | null {
    const read = readJson(json);
    if ("error" in read) return read.error;
    const screenIndex = this.model?.screens.findIndex((screen) => screen.uid === this.selection.screen) ?? 0;
    const model = parse(read.json);
    if (text(model) === text(this.model!)) return null;
    this.apply(model);
    this.selection = { screen: model.screens[Math.max(screenIndex, 0)]?.uid ?? null, block: null };
    return null;
  }

  select(screen: string | null, block: string | null = null) {
    this.selection = { screen, block };
  }

  setPreview(change: Partial<PreviewSettings>) {
    this.preview = { ...this.preview, ...change };
  }

  usedKey(key: string): TemplateRef[] {
    return this.flow?.used_keys[key] ?? [];
  }

  usedInput(key: string): TemplateRef[] {
    return this.flow?.used_inputs[key] ?? [];
  }

  private get canSave(): boolean {
    return !!this.model && this.dirty && !this.readOnly && !this.conflict;
  }

  private scheduleSave() {
    clearTimeout(this.timer);
    if (this.canSave) this.timer = setTimeout(() => this.save(), AUTOSAVE_MS);
  }

  private async saveUntilDone() {
    do {
      this.again = false;
      await this.saveOnce();
    } while (this.again && this.canSave && !this.saveError);
  }

  /** Edits made while the request runs stay unsaved: what was saved is what was sent. */
  private async saveOnce() {
    const sent = this.model!;
    const json = text(sent);
    this.saving = true;
    this.saveError = null;
    try {
      const state = await this.api.save(this.name, json, this.modified);
      this.savedJson = json;
      this.dirty = text(this.model!) !== json;
      this.takeState(state, sent);
    } catch (e) {
      if (isTimestampMismatch(e)) this.conflict = true;
      else this.saveError = e;
    } finally {
      this.saving = false;
    }
  }

  private setSaved(model: FlowModel) {
    this.model = model;
    this.savedJson = text(model);
    this.dirty = false;
    this.checkRules();
  }

  private takeState(state: FlowState, uploaded: FlowModel) {
    this.modified = state.modified;
    this.flow = { ...this.flow!, status: state.status, validation_errors: state.validation_errors };
    this.metaFound = metaProblems(uploaded, state.validation_errors ?? []);
  }

  /** A deleted block hands the selection to its screen; a deleted screen to the first one. */
  private keepSelection(model: FlowModel) {
    const screen = model.screens.find((each) => each.uid === this.selection.screen);
    if (!screen) {
      this.selection = { screen: model.screens[0]?.uid ?? null, block: null };
      return;
    }
    const block = this.selection.block;
    const blockGone = block && !screen.blocks.some((each) => each.uid === block) && screen.footer?.uid !== block;
    if (blockGone) this.selection = { screen: screen.uid, block: null };
  }
}

export function isTimestampMismatch(error: unknown): boolean {
  return (error as { exc_type?: string } | null)?.exc_type === "TimestampMismatchError";
}

/** Which New flow field a server error belongs on. */
export function fieldOfError(error: unknown): "flow_name" | "categories" | null {
  const type = (error as { exc_type?: string } | null)?.exc_type;
  if (type === "FlowNameError") return "flow_name";
  if (type === "FlowCategoriesError") return "categories";
  return null;
}

function text(model: FlowModel): string {
  return JSON.stringify(serialize(model));
}

function flowJson(value: BuilderFlow["flow_json"]): JsonObject | null {
  if (!value) return null;
  return (typeof value === "string" ? JSON.parse(value) : value) as JsonObject;
}
