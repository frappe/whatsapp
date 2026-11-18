import { addBlock } from "./blocks";
import { blockOf, edit, objects, screenOf } from "./edit";
import { footerTarget, isEnding } from "./endings";
import { addScreen, setFooter } from "./screens";
import { screenItems } from "./serialize";
import type { Added, FlowModel, JsonObject, Screen } from "./types";

/**
 * As in Meta's playground, the screens list is the journey: each screen's button goes to the next
 * one and the last finishes the form. A Flow whose JSON says otherwise is kept as written.
 */
export function followsListOrder(model: FlowModel): boolean {
  const journey = journeyScreens(model);
  const linked = journey.every((screen, index) => {
    const next = journey[index + 1];
    return next ? footerTarget(screen) === next.props.id : isEnding(screen);
  });
  return linked && !hasOtherNavigation(model);
}

/** The screens a contact goes through, without the Opt-ins' "Read more" screens. */
export function journeyScreens(model: FlowModel): Screen[] {
  const subScreens = new Set(readMoreLinks(model).map((link) => link.screen));
  return model.screens.filter((screen) => !subScreens.has(screen));
}

/** The "Read more" screen an Opt-in opens. */
export function readMoreOf(model: FlowModel, optInUid: string): Screen | undefined {
  return readMoreLinks(model).find((link) => link.optIn === optInUid)?.screen;
}

/** The Opt-in a "Read more" screen belongs to, with the screen that holds it. */
export function readMoreParent(
  model: FlowModel,
  screenUid: string
): { screen: Screen; optIn: string } | undefined {
  const link = readMoreLinks(model).find((each) => each.screen.uid === screenUid);
  return link && { screen: link.parent, optIn: link.optIn };
}

export function addScreenInJourney(model: FlowModel, { title }: { title: string }): Added {
  const linear = followsListOrder(model);
  const added = addScreen(model, { title, index: lastJourneyIndex(model) + 1 });
  return { model: linear ? linkInOrder(added.model) : added.model, uid: added.uid };
}

/** `index` counts the journey's screens, without the moved one. */
export function moveScreenInJourney(model: FlowModel, uid: string, index: number): FlowModel {
  const linear = followsListOrder(model);
  const moved = edit(model, (draft) => {
    const screen = screenOf(draft, uid);
    draft.screens.splice(draft.screens.indexOf(screen), 1);
    const rest = journeyScreens(draft);
    const at = rest[index] ? draft.screens.indexOf(rest[index]) : lastJourneyIndex(draft) + 1;
    draft.screens.splice(at, 0, screen);
  });
  return linear ? linkInOrder(moved) : moved;
}

export interface RemovedScreens {
  screens: { screen: Screen; index: number }[];
}

/** The screen goes with its "Read more" screens; `restoreScreens` puts them all back. */
export function deleteScreenInJourney(
  model: FlowModel,
  uid: string
): { model: FlowModel; removed: RemovedScreens } {
  const linear = followsListOrder(model);
  const screen = screenOf(model, uid);
  const going = [screen, ...subScreensOf(model, screen)];
  const removed = {
    screens: going.map((each) => ({ screen: clone(each), index: model.screens.indexOf(each) })),
  };
  const changed = edit(model, (draft) => {
    draft.screens = draft.screens.filter((each) => !going.some((gone) => gone.uid === each.uid));
  });
  return { model: linear ? linkInOrder(changed) : changed, removed };
}

export function restoreScreens(model: FlowModel, removed: RemovedScreens): FlowModel {
  const linear = followsListOrder(model);
  const restored = edit(model, (draft) => {
    for (const { screen, index } of [...removed.screens].sort((a, b) => a.index - b.index))
      draft.screens.splice(index, 0, clone(screen));
  });
  return linear ? linkInOrder(restored) : restored;
}

/** Meta puts the "Read more" screen at the end of `screens`, with one Body and no button. */
export function addReadMore(
  model: FlowModel,
  optInUid: string,
  { title, text }: { title: string; text: string }
): Added {
  const screen = addScreen(model, { title });
  let changed = edit(screen.model, (draft) => {
    const sub = screenOf(draft, screen.uid);
    sub.footer = null;
    delete sub.props.terminal;
    const { block } = blockOf(draft, optInUid);
    block.component["on-click-action"] = {
      name: "navigate",
      next: { type: "screen", name: sub.props.id },
      payload: {},
    };
  });
  changed = addBlock(changed, screen.uid, "TextBody", { text }).model;
  return { model: changed, uid: screen.uid };
}

export function removeReadMore(model: FlowModel, optInUid: string): FlowModel {
  const sub = readMoreOf(model, optInUid);
  return edit(model, (draft) => {
    delete blockOf(draft, optInUid).block.component["on-click-action"];
    if (sub) draft.screens = draft.screens.filter((screen) => screen.uid !== sub.uid);
  });
}

/** Rewrites only the buttons that are off, so an already linked Flow stays as written. */
function linkInOrder(model: FlowModel): FlowModel {
  const journey = journeyScreens(model);
  let linked = model;
  journey.forEach((screen, index) => {
    const next = journey[index + 1];
    if (next && footerTarget(screen) !== next.props.id)
      linked = setFooter(linked, screen.uid, { action: { navigate: String(next.props.id) } });
    if (!next && !isEnding(screen)) linked = setFooter(linked, screen.uid, { action: "finish" });
  });
  return linked;
}

interface ReadMoreLink {
  parent: Screen;
  optIn: string;
  screen: Screen;
}

function readMoreLinks(model: FlowModel): ReadMoreLink[] {
  return model.screens.flatMap((parent) =>
    parent.blocks.flatMap((block) => {
      const action = block.component["on-click-action"] as JsonObject | undefined;
      if (block.component.type !== "OptIn" || action?.name !== "navigate") return [];
      const target = (action.next as JsonObject | undefined)?.name;
      const screen = model.screens.find((each) => each.props.id === target && each !== parent);
      return screen ? [{ parent, optIn: block.uid, screen }] : [];
    })
  );
}

function subScreensOf(model: FlowModel, screen: Screen): Screen[] {
  return readMoreLinks(model)
    .filter((link) => link.parent === screen)
    .map((link) => link.screen);
}

/** Any navigation besides the buttons and the Opt-ins' links: an Advanced block or `routing_model`. */
function hasOtherNavigation(model: FlowModel): boolean {
  if (model.flow.routing_model) return true;
  return model.screens.some((screen) =>
    screenItems(screen)
      .filter((item) => item !== screen.footer && item.component.type !== "OptIn")
      .some((item) => [...objects(item.component)].some((object) => object.name === "navigate"))
  );
}

function lastJourneyIndex(model: FlowModel): number {
  const journey = journeyScreens(model);
  return journey.length ? model.screens.indexOf(journey[journey.length - 1]) : -1;
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}
