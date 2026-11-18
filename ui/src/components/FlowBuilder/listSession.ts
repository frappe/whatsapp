import type { CreateFlowArgs, FlowBuilderApi, FlowListRow } from "./types";

/** The Flows list and the calls that add to it. `useFlowList` makes it reactive. */
export class FlowListSession {
  rows: FlowListRow[] = [];
  loading = false;
  loaded = false;
  error: unknown = null;
  syncing = false;
  syncedAt: number | null = null;

  constructor(
    private api: FlowBuilderApi,
    readonly account?: string
  ) {}

  async load() {
    this.loading = true;
    this.error = null;
    try {
      this.rows = await this.api.list(this.account);
      this.loaded = true;
    } catch (e) {
      this.error = e;
    } finally {
      this.loading = false;
    }
  }

  /** Throws the server's error, so the dialog can put it on its field. */
  async create(args: CreateFlowArgs): Promise<string> {
    const name = await this.api.create(args);
    await this.load();
    return name;
  }

  /** Throws the server's refusal, for example while templates use the Flow. */
  async remove(name: string) {
    await this.api.remove(name);
    await this.load();
  }

  async sync() {
    if (!this.account || this.syncing) return;
    this.syncing = true;
    try {
      await this.api.sync(this.account);
      this.syncedAt = Date.now();
      await this.load();
    } finally {
      this.syncing = false;
    }
  }
}
