import { endingAnswers, isEnding } from "./endings";
import type { Block, FlowModel, Footer, Json, JsonObject, Screen } from "./types";

export interface Location {
  screenId: string;
  blockId?: string;
}

export function serialize(model: FlowModel): JsonObject {
  return new Serializer(model).flow();
}

/** Each screen's and block's path in the serialized Flow JSON, e.g. `screens[0].layout.children[1]`. */
export function jsonPaths(model: FlowModel): Map<string, Location> {
  const serializer = new Serializer(model);
  serializer.flow();
  return serializer.paths;
}

/** A screen's blocks and its footer, in the order they are written. */
export function screenItems(screen: Screen): (Block | Footer)[] {
  const items: (Block | Footer)[] = [...screen.blocks];
  const footer = screen.footer;
  if (!footer) return items;
  const after = items.findIndex((block) => block.uid === footer.after);
  const index = footer.after === null ? 0 : after >= 0 ? after + 1 : items.length;
  items.splice(index, 0, footer);
  return items;
}

class Serializer {
  paths = new Map<string, Location>();

  constructor(private model: FlowModel) {}

  flow(): JsonObject {
    const screens = this.model.screens.map((screen, index) => this.screen(screen, `screens[${index}]`));
    return { ...this.model.flow, screens };
  }

  private screen(screen: Screen, path: string): JsonObject {
    this.paths.set(path, { screenId: screen.uid });
    if (!screen.layout) return screen.props;
    const children = this.children(screen, `${path}.layout.children`);
    return { ...screen.props, layout: { ...screen.layout, children } };
  }

  private children(screen: Screen, path: string): Json[] {
    const items = screenItems(screen);
    const first = items.findIndex((item) => item.inForm);
    const last = items.findLastIndex((item) => item.inForm);
    if (!screen.form) return this.place(screen, items, path, 0);
    if (first < 0) return [...this.place(screen, items, path, 0), { ...screen.form, children: [] }];

    const formPath = `${path}[${first}].children`;
    return [
      ...this.place(screen, items.slice(0, first), path, 0),
      { ...screen.form, children: this.place(screen, items.slice(first, last + 1), formPath, 0) },
      ...this.place(screen, items.slice(last + 1), path, first + 1),
    ];
  }

  private place(screen: Screen, items: (Block | Footer)[], path: string, offset: number): Json[] {
    return items.map((item, index) => {
      this.paths.set(`${path}[${offset + index}]`, { screenId: screen.uid, blockId: item.uid });
      return item === screen.footer ? this.footer(screen) : item.component;
    });
  }

  private footer(screen: Screen): JsonObject {
    const footer = screen.footer!;
    if (!isEnding(screen) || footer.customAnswers) return footer.component;
    const action = footer.component["on-click-action"] as JsonObject;
    const payload = endingAnswers(this.model, screen.uid);
    return { ...footer.component, "on-click-action": { ...action, payload } };
  }
}
