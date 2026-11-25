import { endingAnswers, isEnding } from "./endings";
import type { Block, FlowModel, Footer, Json, JsonObject, Screen } from "./types";

/** Every key the model does not edit is kept as written, in place. */
export function parse(json: JsonObject): FlowModel {
  return new Parser().parse(json);
}

class Parser {
  private nextUid = 1;

  parse(json: JsonObject): FlowModel {
    const screens = Array.isArray(json.screens) ? json.screens : [];
    const model: FlowModel = {
      flow: { ...json, screens: null },
      screens: screens.map((screen) => this.screen(screen as JsonObject)),
      nextUid: 0,
    };
    model.nextUid = this.nextUid;
    markCustomAnswers(model);
    return model;
  }

  private screen(json: JsonObject): Screen {
    const screen: Screen = {
      uid: this.uid("s"),
      props: json,
      layout: null,
      form: null,
      blocks: [],
      footer: null,
    };
    const layout = json.layout;
    if (isObject(layout) && Array.isArray(layout.children)) {
      screen.props = { ...json, layout: null };
      screen.layout = { ...layout, children: null };
      this.children(screen, layout.children, false);
    }
    if (screen.footer?.after === lastUid(screen)) delete screen.footer.after;
    return screen;
  }

  private children(screen: Screen, children: Json[], inForm: boolean) {
    for (const child of children) {
      const component = child as JsonObject;
      if (!inForm && !screen.form && component?.type === "Form" && Array.isArray(component.children)) {
        screen.form = { ...component, children: null };
        this.children(screen, component.children, true);
      } else if (!screen.footer && component?.type === "Footer") {
        screen.footer = this.footer(component, inForm, lastUid(screen));
      } else {
        screen.blocks.push(this.block(component, inForm));
      }
    }
  }

  private footer(component: JsonObject, inForm: boolean, after: string | null): Footer {
    return { uid: this.uid("f"), component, inForm, after, customAnswers: false };
  }

  private block(component: JsonObject, inForm: boolean): Block {
    return { uid: this.uid("b"), component, inForm };
  }

  private uid(prefix: string): string {
    return `${prefix}${this.nextUid++}`;
  }
}

function markCustomAnswers(model: FlowModel) {
  for (const screen of model.screens) {
    if (!screen.footer || !isEnding(screen)) continue;
    const written = (screen.footer.component["on-click-action"] as JsonObject).payload;
    screen.footer.customAnswers =
      JSON.stringify(written) !== JSON.stringify(endingAnswers(model, screen.uid));
  }
}

function lastUid(screen: Screen): string | null {
  return screen.blocks.at(-1)?.uid ?? null;
}

export function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
