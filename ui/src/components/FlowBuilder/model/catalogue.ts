import type { Block, Json, JsonObject } from "./types";

export const FLOW_JSON_VERSION = "7.3";

export interface BlockKind {
  /** As the editor's Add content names it, so rule messages use the same words. */
  name: string;
  /** The property that holds what the admin reads on the block. */
  textKey: "text" | "label" | "alt-text";
  /** A question writes an answer under its `name`. */
  question: boolean;
  choices: boolean;
  defaults: JsonObject;
}

const OPTIONS: Json = [
  { id: "option_1", title: "Option 1" },
  { id: "option_2", title: "Option 2" },
];

function text(name: string): BlockKind {
  return { name, textKey: "text", question: false, choices: false, defaults: {} };
}

function question(name: string): BlockKind {
  return { name, textKey: "label", question: true, choices: false, defaults: {} };
}

function choice(name: string): BlockKind {
  return { name, textKey: "label", question: true, choices: true, defaults: { "data-source": OPTIONS } };
}

export const BLOCK_KINDS: Record<string, BlockKind> = {
  TextHeading: text("Large heading"),
  TextSubheading: text("Small heading"),
  TextBody: text("Body"),
  TextCaption: text("Caption"),
  RichText: text("Rich text"),
  TextInput: question("Short answer"),
  TextArea: question("Paragraph"),
  Dropdown: choice("Dropdown"),
  RadioButtonsGroup: choice("Single choice"),
  CheckboxGroup: choice("Multiple choice"),
  ChipsSelector: choice("Chips"),
  DatePicker: question("Date picker"),
  CalendarPicker: question("Calendar"),
  OptIn: question("Opt-in"),
  PhotoPicker: question("Photo"),
  DocumentPicker: question("Document"),
  Image: {
    name: "Image",
    textKey: "alt-text",
    question: false,
    choices: false,
    defaults: {},
  },
  EmbeddedLink: {
    name: "Link",
    textKey: "text",
    question: false,
    choices: false,
    defaults: { "on-click-action": { name: "open_url", url: "" } },
  },
};

/** Character limits from Meta's component reference. TextCaption's 409 is as the reference prints it. */
export const TEXT_LIMITS: Record<string, Record<string, number>> = {
  TextHeading: { text: 80 },
  TextSubheading: { text: 80 },
  TextBody: { text: 4096 },
  TextCaption: { text: 409 },
  TextInput: { label: 20, "helper-text": 80, "error-message": 30 },
  TextArea: { label: 20, "helper-text": 80 },
  Dropdown: { label: 20 },
  RadioButtonsGroup: { label: 30, description: 300 },
  CheckboxGroup: { label: 30, description: 300 },
  ChipsSelector: { label: 80, description: 300 },
  DatePicker: { label: 40, "helper-text": 80, "error-message": 80 },
  CalendarPicker: { label: 40, title: 80, description: 300, "helper-text": 80, "error-message": 80 },
  OptIn: { label: 120 },
  EmbeddedLink: { text: 25 },
  Footer: { label: 35, "left-caption": 15, "center-caption": 15, "right-caption": 15 },
};

export const OPTION_LIMITS: Record<string, number> = { title: 30, description: 300, metadata: 20 };

export const OPTION_COUNTS: Record<string, { min: number; max: number }> = {
  Dropdown: { min: 1, max: 200 },
  RadioButtonsGroup: { min: 1, max: 20 },
  CheckboxGroup: { min: 1, max: 20 },
  ChipsSelector: { min: 2, max: 20 },
};

/** Dropdown allows 100 options when any option has an image. */
export const DROPDOWN_MAX_WITH_IMAGES = 100;

export const SCREEN_LIMITS = { components: 50, OptIn: 5, EmbeddedLink: 2, Image: 3 };

export const RESERVED_SCREEN_IDS = ["SUCCESS"];

const OPEN_URL_TYPES = ["EmbeddedLink", "OptIn"];

/** The text kinds Meta's "Type" select converts between. */
export const TEXT_TYPES = ["TextHeading", "TextSubheading", "TextBody", "TextCaption"];

/** Meta's Image reference: JPEG or PNG, 300 KB at most. */
export const IMAGE_FILE = { maxBytes: 300 * 1024, types: ["image/jpeg", "image/png"] };

export function kindOf(block: Block): BlockKind | undefined {
  return isAdvanced(block) ? undefined : BLOCK_KINDS[String(block.component.type)];
}

/** A block the builder keeps as written: an unknown component, or one with actions other than open_url. */
export function isAdvanced(block: Block): boolean {
  const component = block.component;
  const kind = BLOCK_KINDS[String(component.type)];
  if (!kind) return true;
  if (kind.choices && !Array.isArray(component["data-source"])) return true;
  return Object.entries(component).some(
    ([key, value]) =>
      key.endsWith("-action") && !isOpenUrl(String(component.type), value) && !isReadMore(component, key)
  );
}

export function isQuestion(block: Block): boolean {
  return Boolean(kindOf(block)?.question);
}

/** An Opt-in's "Read more" link to a screen of its own. */
function isReadMore(component: JsonObject, key: string): boolean {
  const action = component[key] as JsonObject | undefined;
  return component.type === "OptIn" && key === "on-click-action" && action?.name === "navigate";
}

function isOpenUrl(type: string, action: Json): boolean {
  return OPEN_URL_TYPES.includes(type) && (action as JsonObject)?.name === "open_url";
}
