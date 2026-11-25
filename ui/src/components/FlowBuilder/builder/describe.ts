import { footerTarget, isEnding, kindOf, type Block, type FlowModel, type Screen } from "../model";
import { format, type FlowBuilderChrome } from "../chrome";

/** Meta's "Add content" groups and names; the types Meta's playground leaves out are added to them. */
export const CONTENT_MENU = [
  { group: "Text", icon: "lucide-type", types: ["TextHeading", "TextSubheading", "TextCaption", "TextBody", "RichText"] },
  { group: "Media", icon: "lucide-image", types: ["Image", "PhotoPicker", "DocumentPicker", "EmbeddedLink"] },
  { group: "TextAnswer", icon: "lucide-text-cursor-input", types: ["TextInput", "TextArea", "DatePicker", "CalendarPicker"] },
  {
    group: "Selection",
    icon: "lucide-list",
    types: ["RadioButtonsGroup", "CheckboxGroup", "Dropdown", "ChipsSelector", "OptIn"],
  },
] as const;

export const INPUT_TYPES = ["text", "password", "email", "number", "passcode", "phone"] as const;

/** "Short answer", or the type of an Advanced block. */
export function kindName(block: Block, chrome: FlowBuilderChrome): string {
  const type = String(block.component.type ?? "");
  if (!kindOf(block)) return type || "?";
  return chrome[type as keyof FlowBuilderChrome] ?? type;
}

/** The muted part of a collapsed row: what the admin wrote on the block. */
export function blockSummary(block: Block, chrome: FlowBuilderChrome): string {
  const kind = kindOf(block);
  if (!kind) return chrome.shownInJson;
  const text = block.component[kind.textKey];
  if (Array.isArray(text)) return text.join(" ");
  return typeof text === "string" ? text : "";
}

export function screenTitle(screen: Screen, model: FlowModel, chrome: FlowBuilderChrome): string {
  const title = screen.props.title;
  return typeof title === "string" && title.trim()
    ? title
    : format(chrome.untitledScreen, model.screens.indexOf(screen) + 1);
}

/** Where a button goes when the Flow JSON, not the list order, decides it. */
export function setInJson(screen: Screen, model: FlowModel, chrome: FlowBuilderChrome): string {
  if (isEnding(screen)) return chrome.endsForm;
  const target = footerTarget(screen);
  const next = model.screens.find((each) => each.props.id === target);
  return format(chrome.goesTo, next ? screenTitle(next, model, chrome) : target || "?");
}

export function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}
