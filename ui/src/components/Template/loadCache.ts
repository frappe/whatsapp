import { reactive, shallowReactive } from "vue";
import type { Loaded } from "./types";

const PENDING: Loaded<never> = Object.freeze({
  data: undefined,
  loading: true,
  error: null,
  retry() {},
});

/**
 * Fetches each key once and keeps the result, so every picker on the same key shares one
 * request. `get` is safe to call from a render: the fetch starts on the next microtask.
 */
export class LoadCache<T> {
  private entries = shallowReactive(new Map<string, Loaded<T>>());
  private scheduled = new Set<string>();

  constructor(private fetcher: (...parts: string[]) => Promise<T>) {}

  get(...parts: string[]): Loaded<T> {
    const key = JSON.stringify(parts);
    const entry = this.entries.get(key);
    if (entry) return entry;
    if (!this.scheduled.has(key)) {
      this.scheduled.add(key);
      queueMicrotask(() => this.create(key, parts));
    }
    return PENDING;
  }

  clear() {
    this.entries.clear();
    this.scheduled.clear();
  }

  private create(key: string, parts: string[]) {
    const entry: Loaded<T> = reactive({
      data: undefined,
      loading: false,
      error: null,
      retry: () => this.load(entry, parts),
    }) as Loaded<T>;
    this.entries.set(key, entry);
    this.load(entry, parts);
  }

  private async load(entry: Loaded<T>, parts: string[]) {
    entry.loading = true;
    entry.error = null;
    try {
      entry.data = (await this.fetcher(...parts)) as never;
    } catch (e) {
      entry.error = e;
    } finally {
      entry.loading = false;
    }
  }
}
