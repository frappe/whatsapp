import { nextTick, reactive } from "vue";
import type { Problem, Screen } from "../model";
import type { BuilderSession } from "../session";

/** The "Screen title" row has no block of its own, so it is keyed by its screen. */
export function titleRow(screenUid: string): string {
  return `title:${screenUid}`;
}

/**
 * Which "Edit content" rows are open, and the way to one from elsewhere: the header's problem
 * count today, a click in the preview later. A row's id is its block or footer uid.
 */
export class ContentRows {
  private open = reactive(new Set<string>());
  private container: HTMLElement | null = null;

  constructor(private session: BuilderSession) {}

  attach(container: HTMLElement | null) {
    this.container = container;
  }

  isOpen(id: string): boolean {
    return this.open.has(id);
  }

  toggle(screen: Screen, id: string) {
    if (this.open.has(id)) this.open.delete(id);
    else this.openRow(screen, id);
  }

  openRow(screen: Screen, id: string) {
    this.open.add(id);
    this.session.select(screen.uid, id === titleRow(screen.uid) ? null : id);
  }

  /** Selects the screen, opens the row and scrolls it into view once it is drawn. */
  async reveal(screenUid: string, id: string | null) {
    const row = id ?? titleRow(screenUid);
    this.open.add(row);
    this.session.select(screenUid, id);
    await nextTick();
    const element = this.container?.querySelector<HTMLElement>(`[data-row="${CSS.escape(row)}"]`);
    element?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  revealProblem(problem: Problem) {
    if (problem.screenId) this.reveal(problem.screenId, problem.blockId ?? null);
  }
}
