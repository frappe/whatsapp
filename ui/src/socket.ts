import { getCurrentInstance, inject } from "vue";

export interface RealtimeSocket {
  emit(event: string, ...args: unknown[]): void;
  on(event: string, handler: (...args: unknown[]) => void): void;
  off(event: string, handler: (...args: unknown[]) => void): void;
}

/**
 * Resolve the host's socket.io connection, without this package owning one.
 *
 * A host exposes it either by `provide("socket", …)` / `provide("$socket", …)` at the app
 * root or as an `app.config.globalProperties.$socket` global; both are tried, in that order.
 * Must be called during `setup()`, since injection is only possible there.
 *
 * This mirrors `@framework/ui`'s helper rather than importing it — this package takes no
 * dependency on that one.
 */
export function getSocketInstance(): RealtimeSocket | undefined {
  const instance = getCurrentInstance();
  if (!instance) {
    throw new Error("getSocketInstance() must be called during setup().");
  }

  const globals = instance.appContext.config.globalProperties;
  const socket =
    inject<RealtimeSocket | undefined>("socket", undefined) ??
    inject<RealtimeSocket | undefined>("$socket", undefined) ??
    (globals.socket as RealtimeSocket | undefined) ??
    (globals.$socket as RealtimeSocket | undefined);

  if (!socket && import.meta.env?.DEV) {
    console.warn(
      "getSocketInstance: no socket found. Live message updates are off. " +
        "Expose one via provide('socket'|'$socket', …) or a $socket global."
    );
  }

  return socket;
}
