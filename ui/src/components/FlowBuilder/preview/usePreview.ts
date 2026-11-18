import { markRaw, onScopeDispose, reactive, shallowRef, watch } from "vue";
import { debounce } from "frappe-ui";
import type { FlowModel } from "../model";
import type { BuilderSession } from "../session";
import type { ContentRows } from "../builder/rows";
import { titleRow } from "../builder/rows";
import { PreviewRun } from "./interactive";

const SETTLE_MS = 300;

/**
 * The model the phone draws and the run through it. Typing reaches the phone once it pauses;
 * picking another screen, or a mode change, reaches it at once. In Interactive mode the left
 * column follows the phone's screen.
 */
export function usePreview(session: BuilderSession, rows: ContentRows) {
  const shown = shallowRef<FlowModel>(session.model!);
  // The run holds the model; markRaw keeps Vue from wrapping every screen of it in a proxy.
  const run = reactive(new PreviewRun(markRaw(session.model!))) as PreviewRun;
  const settleLater = debounce(settle, SETTLE_MS);

  function settle() {
    settleLater.cancel();
    if (!session.model || shown.value === session.model) return;
    shown.value = session.model;
    run.sync(markRaw(session.model));
  }

  watch(() => session.model, settleLater);

  watch(
    () => session.selection.screen,
    (uid) => {
      if (uid === run.screen?.uid && !run.sent) return;
      settle();
      run.show(uid);
    },
    { immediate: true }
  );

  watch(
    () => session.preview.interactive,
    (on) => {
      settle();
      if (on) run.start();
      else run.show(session.selection.screen);
    }
  );

  watch(
    () => run.screen?.uid,
    (uid) => {
      const screen = shown.value.screens.find((each) => each.uid === uid);
      if (!session.preview.interactive || !screen || uid === session.selection.screen) return;
      rows.openRow(screen, titleRow(screen.uid));
    }
  );

  onScopeDispose(settleLater.cancel);
  return { shown, run };
}
