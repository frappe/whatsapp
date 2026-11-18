import { dialog } from "frappe-ui";
import {
  answerKey,
  clearPrefill,
  kindOf,
  prefillKey,
  renameAnswerKey,
  setPrefill,
  uniqueAnswerKey,
  updateBlock,
  type Block,
  type Screen,
} from "../model";
import { format, type FlowBuilderChrome } from "../chrome";
import type { BuilderSession } from "../session";
import type { TemplateRef } from "../types";

/**
 * Edits that need more than one model operation, or a question first. A question's answer key
 * follows its text while the key is still the generated one and no template maps it.
 */
export class BlockActions {
  constructor(
    private session: BuilderSession,
    private chrome: () => FlowBuilderChrome
  ) {}

  setText(block: Block, value: string) {
    const kind = kindOf(block);
    if (!kind) return;
    let model = updateBlock(this.session.model!, block.uid, { [kind.textKey]: value });
    const key = String(block.component.name ?? "");
    const old = String(block.component[kind.textKey] ?? "");
    if (kind.question && this.followsText(key, old) && !this.session.usedKey(key).length) {
      const next = answerKey(value);
      if (next !== key) model = renameAnswerKey(model, block.uid, uniqueAnswerKey(model, value));
    }
    this.session.apply(model);
  }

  /** Templates that map the old key would warn about it, so ask first. */
  renameKey(block: Block, key: string, onCancel: () => void) {
    const old = String(block.component.name);
    if (!key || key === old) return onCancel();
    const rename = () => this.session.apply(renameAnswerKey(this.session.model!, block.uid, key));
    const used = this.session.usedKey(old);
    if (!used.length) return rename();
    dialog.confirm({
      title: this.chrome().renameKeyTitle,
      message: format(this.chrome().renameKeyMessage, templates(used), old, key),
      theme: "amber",
      confirmLabel: this.chrome().rename,
      onConfirm: rename,
      onCancel,
    });
  }

  /** Turning prefill off drops the key that templates fill, so warn first. */
  setPrefill(screen: Screen, block: Block, on: boolean) {
    const model = this.session.model!;
    if (on) {
      this.session.apply(setPrefill(model, block.uid, { example: String(block.component.label ?? "") }));
      return;
    }
    const key = prefillKey(screen, block);
    const clear = () => this.session.apply(clearPrefill(this.session.model!, block.uid));
    const used = key ? this.session.usedInput(key) : [];
    if (!used.length) return clear();
    dialog.confirm({
      title: this.chrome().prefillOffTitle,
      message: format(this.chrome().prefillOffMessage, templates(used), key!),
      theme: "amber",
      confirmLabel: this.chrome().stopPrefill,
      onConfirm: clear,
    });
  }

  private followsText(key: string, text: string): boolean {
    const generated = answerKey(text);
    return key === generated || new RegExp(`^${generated}_\\d+$`).test(key);
  }
}

function templates(used: TemplateRef[]): string {
  return used.map((template) => template.template_label || template.name).join(", ");
}
