import { computed, inject, provide, type ComputedRef, type InjectionKey } from "vue";
import { FLOW_BUILDER_CHROME, type FlowBuilderChrome } from "./chrome";
import type { ContentRows } from "./builder/rows";
import type { BuilderSession } from "./session";
import type { FlowModel } from "./model";

export interface BuilderContext {
  session: BuilderSession;
  chrome: ComputedRef<FlowBuilderChrome>;
  rows: ContentRows;
  /** Applies a model operation; does nothing on a read-only Flow. */
  edit: (change: (model: FlowModel) => FlowModel) => void;
}

const KEY: InjectionKey<BuilderContext> = Symbol("FlowBuilder");

export function provideBuilder(context: BuilderContext) {
  provide(KEY, context);
}

export function useBuilder(): BuilderContext {
  const context = inject(KEY);
  if (!context) throw new Error("A Flow builder part must be inside FlowBuilder");
  return context;
}

export function useChrome(chrome: () => Partial<FlowBuilderChrome> | undefined) {
  return computed(() => ({ ...FLOW_BUILDER_CHROME, ...chrome() }));
}
