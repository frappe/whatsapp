import { inject, provide, type InjectionKey } from "vue";
import type { Block, FlowModel, Screen } from "../model";
import type { PreviewSettings } from "../types";
import type { PreviewRun } from "./interactive";
import { sampleText } from "./sample";

/** What every renderer inside the phone reads. Getters, so renderers stay reactive. */
export interface Phone {
  readonly model: FlowModel;
  readonly screen: Screen;
  readonly run: PreviewRun;
  readonly settings: PreviewSettings;
  /** The component whose row is being edited; none in Interactive mode. */
  readonly highlight: string | null;
  /** Text with `${…}` references filled in. */
  text(value: unknown): string;
  /** The Dropdown whose options cover the sheet. */
  readonly sheet: Block | null;
  openSheet(block: Block): void;
  closeSheet(): void;
  pick(blockUid: string): void;
}

const KEY: InjectionKey<Phone> = Symbol("FlowBuilderPhone");

export function providePhone(phone: Omit<Phone, "text">) {
  const full: Phone = Object.defineProperties(
    { text: (value: unknown) => sampleText(value, full.model, full.screen, full.run.filled) } as Phone,
    Object.getOwnPropertyDescriptors(phone)
  );
  provide(KEY, full);
  return full;
}

export function usePhone(): Phone {
  const phone = inject(KEY);
  if (!phone) throw new Error("A phone renderer must be inside the preview's phone");
  return phone;
}
