export type Json = null | boolean | number | string | Json[] | JsonObject;
export type JsonObject = { [key: string]: Json };

/**
 * An editable Flow. Every screen, block and footer keeps its own JSON object, so keys the
 * builder does not know survive in place. `uid`s are internal and never serialized.
 */
export interface FlowModel {
  /** The Flow JSON; its `screens` key only holds the place. */
  flow: JsonObject;
  screens: Screen[];
  nextUid: number;
}

export interface Screen {
  uid: string;
  /** The screen JSON; its `layout` key only holds the place. */
  props: JsonObject;
  /** The layout JSON without `children`, or null when the screen has no usable layout. */
  layout: JsonObject | null;
  /** The first Form of the layout, without `children`. Its blocks have `inForm`. */
  form: JsonObject | null;
  blocks: Block[];
  footer: Footer | null;
}

export interface Block {
  uid: string;
  component: JsonObject;
  inForm: boolean;
}

export interface Footer {
  uid: string;
  component: JsonObject;
  inForm: boolean;
  /** The block the footer follows; undefined means after every block. */
  after?: string | null;
  /** The `complete` payload is kept as written instead of being generated. */
  customAnswers: boolean;
}

export type FooterAction = { navigate: string } | "finish";

export interface Added {
  model: FlowModel;
  uid: string;
}

export type Severity = "error" | "warning";

export interface Problem {
  severity: Severity;
  code: string;
  message: string;
  screenId: string;
  blockId?: string;
  /** Where the problem is in the serialized Flow JSON, e.g. `screens[0].layout.children[1]`. */
  path?: string;
}
