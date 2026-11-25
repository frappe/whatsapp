import {
  BLOCK_KINDS,
  DROPDOWN_MAX_WITH_IMAGES,
  OPTION_COUNTS,
  OPTION_LIMITS,
  SCREEN_LIMITS,
  TEXT_LIMITS,
  isAdvanced,
  kindOf,
} from "./catalogue";
import { objects } from "./edit";
import type { Reporter } from "./rules";
import { screenItems } from "./serialize";
import type { Block, FlowModel, Footer, Json, JsonObject, Screen } from "./types";

const FIELD_NAMES: Record<string, string> = {
  text: "Text",
  "helper-text": "Hint",
  "error-message": "Error message",
  description: "Description",
  title: "Title",
  metadata: "Metadata",
  "left-caption": "Caption",
  "center-caption": "Caption",
  "right-caption": "Caption",
};

/** Empty texts, Meta's documented character limits, option counts and components per screen. */
export function limitProblems(model: FlowModel, report: Reporter) {
  for (const screen of model.screens) {
    for (const block of screen.blocks) if (!isAdvanced(block)) checkBlock(report, screen, block);
    if (screen.footer) checkFooter(report, screen, screen.footer);
    checkScreenCounts(report, screen);
  }
}

function checkFooter(report: Reporter, screen: Screen, footer: Footer) {
  if (isBlank(footer.component.label))
    report.add("error", "empty-text", "The button has no label.", screen, footer, "label");
  checkLengths(report, screen, footer, TEXT_LIMITS.Footer, footer.component, "", "Button label");
}

function checkBlock(report: Reporter, screen: Screen, block: Block) {
  const kind = kindOf(block)!;
  const type = String(block.component.type);
  const value = block.component[kind.textKey];
  if (kind.textKey !== "alt-text" && isBlank(value)) {
    const message = kind.question ? "A question has no text." : "A text block is empty.";
    report.add("error", "empty-text", message, screen, block, kind.textKey);
  }
  checkLengths(
    report,
    screen,
    block,
    TEXT_LIMITS[type] ?? {},
    block.component,
    "",
    kind.question ? "Question" : "Text"
  );
  if (type === "Image" && isBlank(block.component.src))
    report.add("error", "empty-image", "An image must be selected.", screen, block, "src");
  if (kind.choices) checkOptions(report, screen, block);
}

function checkOptions(report: Reporter, screen: Screen, block: Block) {
  const type = String(block.component.type);
  const options = block.component["data-source"] as JsonObject[];
  const label = `"${block.component.label ?? BLOCK_KINDS[type].name}"`;
  const { min, max } = OPTION_COUNTS[type];
  const limit =
    type === "Dropdown" && options.some((option) => option.image) ? DROPDOWN_MAX_WITH_IMAGES : max;
  if (!options.length)
    report.add("error", "no-options", `${label} has no options.`, screen, block, "data-source");
  else if (options.length < min)
    report.add(
      "error",
      "too-few-options",
      `${label} needs at least ${min} options.`,
      screen,
      block,
      "data-source"
    );
  if (options.length > limit) {
    report.add(
      "error",
      "too-many-options",
      `${label} has ${options.length} options. WhatsApp allows ${limit}.`,
      screen,
      block,
      "data-source"
    );
  }
  options.forEach((option, index) => {
    const prefix = `data-source[${index}].`;
    if (isBlank(option.title))
      report.add(
        "error",
        "empty-text",
        `An option of ${label} has no title.`,
        screen,
        block,
        `${prefix}title`
      );
    checkLengths(report, screen, block, OPTION_LIMITS, option, prefix, "Option");
  });
}

function checkLengths(
  report: Reporter,
  screen: Screen,
  item: Block | Footer,
  limits: Record<string, number>,
  values: JsonObject,
  prefix: string,
  labelName: string
) {
  for (const [property, limit] of Object.entries(limits)) {
    const value = values[property];
    if (typeof value !== "string" || value.includes("${") || value.length <= limit) continue;
    const field =
      property === "label" || (prefix && property === "title") ? labelName : FIELD_NAMES[property];
    const message = `${field} is ${value.length} characters long. WhatsApp allows ${limit}.`;
    report.add("error", "text-too-long", message, screen, item, `${prefix}${property}`);
  }
}

function checkScreenCounts(report: Reporter, screen: Screen) {
  const types = screenItems(screen).flatMap((item) =>
    [...objects(item.component)].map((object) => object.type).filter((type) => typeof type === "string")
  );
  const count = (type: string) => types.filter((each) => each === type).length;
  const over: [string, number, number][] = [
    ["components", types.length, SCREEN_LIMITS.components],
    ["agreements", count("OptIn"), SCREEN_LIMITS.OptIn],
    ["links", count("EmbeddedLink"), SCREEN_LIMITS.EmbeddedLink],
    ["images", count("Image"), SCREEN_LIMITS.Image],
  ];
  for (const [what, found, limit] of over) {
    if (found > limit)
      report.add(
        "error",
        "too-many-on-screen",
        `A screen can have ${limit} ${what}. This one has ${found}.`,
        screen
      );
  }
}

function isBlank(value: Json | undefined): boolean {
  if (Array.isArray(value)) return value.every(isBlank);
  return typeof value !== "string" || !value.trim();
}
