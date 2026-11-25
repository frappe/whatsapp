import { onScopeDispose, shallowReactive, watch } from "vue";
import { debounce } from "frappe-ui";
import { frappeFlowApi } from "./api";
import { FlowListSession } from "./listSession";
import { BuilderSession } from "./session";
import type { FlowBuilderApi } from "./types";

const RULES_DELAY_MS = 300;

/**
 * Opens one Flow for the builder. Every edit replaces the model, so a shallow proxy is enough;
 * the rules run once typing pauses, and the session saves once it pauses longer.
 */
export function useFlowBuilder({
  name,
  canWrite = true,
  api = frappeFlowApi,
}: {
  name: string;
  canWrite?: boolean;
  api?: FlowBuilderApi;
}) {
  const session = shallowReactive(new BuilderSession(api, name, canWrite)) as BuilderSession;
  const checkRules = debounce(() => session.checkRules(), RULES_DELAY_MS);
  watch(
    () => session.model,
    (_model, previous) => previous && checkRules()
  );
  onScopeDispose(() => {
    checkRules.cancel();
    session.dispose();
  });
  session.load();
  return session;
}

/** The Flows of one account's business, or of every business without `account`. */
export function useFlowList({ account, api = frappeFlowApi }: { account?: string; api?: FlowBuilderApi } = {}) {
  const list = shallowReactive(new FlowListSession(api, account)) as FlowListSession;
  list.load();
  return list;
}
