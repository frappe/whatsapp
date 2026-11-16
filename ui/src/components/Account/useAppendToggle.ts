import { computed, type WritableComputedRef } from "vue";
import type { AccountController, AppendToggleRow } from "./types";

/**
 * A host setting that switches one managed append action on or off: true while the account
 * has a row for `row.append_to`. Switching on adds `row` (copied), off removes it; a row
 * already there is kept as it is, so turning a setting on never overwrites saved mappings.
 */
export function useAppendToggle(
  controller: AccountController,
  row: AppendToggleRow
): WritableComputedRef<boolean> {
  const isRow = (action: { append_to: string }) => action.append_to === row.append_to;

  return computed({
    get: () => controller.doc.append_actions.some(isRow),
    set: (on: boolean) => {
      const actions = controller.doc.append_actions;
      if (on === actions.some(isRow)) return;
      controller.doc.append_actions = on
        ? [...actions, { ...row }]
        : actions.filter((action) => !isRow(action));
    },
  });
}
