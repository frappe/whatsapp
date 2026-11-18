import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BuilderSession, fieldOfError } from "../../src/components/FlowBuilder/session";
import { FlowListSession } from "../../src/components/FlowBuilder/listSession";
import type { BuilderFlow, FlowBuilderApi, FlowState } from "../../src/components/FlowBuilder/types";
import { addBlock, deleteBlock, renameScreen, serialize, updateBlock } from "../../src/components/FlowBuilder/model";
import { flowJson } from "./fixtures";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function serverFlow(overrides: Partial<BuilderFlow> = {}): BuilderFlow {
  return {
    name: "1200",
    flow_name: "Lead capture",
    flow_json: JSON.stringify(flowJson("builder", "lead_capture")),
    status: "Draft",
    whatsapp_account: "Sales Line",
    business_id: "biz",
    categories: ["LEAD_GENERATION"],
    preview_url: null,
    modified: "2026-11-18 10:00:00.000000",
    validation_errors: [],
    used_keys: { email: [{ name: "T1", template_label: "Welcome" }] },
    used_inputs: {},
    ...overrides,
  };
}

function fakeApi(flow = serverFlow()) {
  let modified = flow.modified;
  const api = {
    get: vi.fn(async () => ({ ...flow, modified })),
    save: vi.fn(async (_name: string, _json: string, sent: string): Promise<FlowState> => {
      if (sent !== modified) throw Object.assign(new Error("changed"), { exc_type: "TimestampMismatchError" });
      modified = `${modified}+`;
      return { status: "Draft", modified, validation_errors: [] };
    }),
    publish: vi.fn(async (): Promise<FlowState> => ({ status: "Published", modified, validation_errors: [] })),
    touch: () => (modified = "elsewhere"),
  };
  return api;
}

async function opened(api = fakeApi()) {
  const session = new BuilderSession(api as unknown as FlowBuilderApi, "1200");
  await session.load();
  return { session, api };
}

/** Holds each save until `release()`, which lets the oldest one through. */
function holdSaves(api: ReturnType<typeof fakeApi>) {
  const answer = api.save.getMockImplementation()!;
  const waiting: (() => void)[] = [];
  api.save.mockImplementation(
    (...args) => new Promise<void>((resolve) => waiting.push(resolve)).then(() => answer(...args))
  );
  return {
    async release() {
      waiting.shift()!();
      await vi.advanceTimersByTimeAsync(0);
    },
  };
}

function rename(session: BuilderSession, title: string) {
  session.apply(renameScreen(session.model!, session.model!.screens[0].uid, title));
}

describe("opening a Flow", () => {
  it("is saved, selects the first screen and runs the rules", async () => {
    const { session } = await opened();

    expect(session.saveState).toBe("saved");
    expect(session.selection).toEqual({ screen: session.model!.screens[0].uid, block: null });
    expect(session.localProblems).toEqual([]);
    expect(session.readOnly).toBe(false);
  });

  it("is read only once the Flow left Draft", async () => {
    const { session } = await opened(fakeApi(serverFlow({ status: "Published" })));

    expect(session.readOnly).toBe(true);
    expect(() => rename(session, "Hi")).toThrow();
  });

  it("locates Meta's stored validation errors on the blocks", async () => {
    const errors = [
      { error: "INVALID_PROPERTY", message: "Bad label", pointers: [{ path: "screens[0].layout.children[1].label" }] },
    ];
    const { session } = await opened(fakeApi(serverFlow({ validation_errors: errors })));

    expect(session.problems).toMatchObject([
      { code: "INVALID_PROPERTY", blockId: session.model!.screens[0].blocks[1].uid },
    ]);
    expect(session.publishBlocker).toEqual({ reason: "errors", count: 1 });
  });
});

describe("editing", () => {
  it("is saving from the first change and saved again when undone by hand", async () => {
    const { session } = await opened();
    rename(session, "About you");
    expect(session.saveState).toBe("saving");

    rename(session, "Your details");
    expect(session.saveState).toBe("saved");
  });

  it("hands the selection to the screen when the selected block is deleted", async () => {
    const { session } = await opened();
    const [screen] = session.model!.screens;
    session.select(screen.uid, screen.blocks[1].uid);

    session.apply(deleteBlock(session.model!, screen.blocks[1].uid));

    expect(session.selection).toEqual({ screen: screen.uid, block: null });
  });
});

describe("autosave", () => {
  it("saves once, 1500 ms after the last change", async () => {
    const { session, api } = await opened();
    rename(session, "About you");
    await vi.advanceTimersByTimeAsync(1000);
    rename(session, "About us");
    await vi.advanceTimersByTimeAsync(1499);
    expect(api.save).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);

    expect(api.save).toHaveBeenCalledTimes(1);
    expect(api.save.mock.calls[0][1]).toBe(JSON.stringify(serialize(session.model!)));
    expect(session.saveState).toBe("saved");
  });

  it("sends the current modified and keeps the returned one", async () => {
    const { session, api } = await opened();
    rename(session, "About you");
    await vi.advanceTimersByTimeAsync(1500);
    rename(session, "About us");
    await vi.advanceTimersByTimeAsync(1500);

    expect(api.save.mock.calls.map((call) => call[2])).toEqual([
      "2026-11-18 10:00:00.000000",
      "2026-11-18 10:00:00.000000+",
    ]);
  });

  it("runs one save at a time and saves the changes made during it once more", async () => {
    const { session, api } = await opened();
    const held = holdSaves(api);
    rename(session, "About you");
    await vi.advanceTimersByTimeAsync(1500);
    rename(session, "About us");
    await vi.advanceTimersByTimeAsync(1500);
    rename(session, "About them");
    await vi.advanceTimersByTimeAsync(1500);
    expect(api.save).toHaveBeenCalledTimes(1);

    await held.release();
    expect(api.save).toHaveBeenCalledTimes(2);
    expect(api.save.mock.calls[1][1]).toBe(JSON.stringify(serialize(session.model!)));
    await held.release();

    expect(session.saveState).toBe("saved");
    await vi.advanceTimersByTimeAsync(5000);
    expect(api.save).toHaveBeenCalledTimes(2);
  });

  it("stops on a change made elsewhere until the Flow is reloaded", async () => {
    const { session, api } = await opened();
    api.touch();
    rename(session, "About you");
    await vi.advanceTimersByTimeAsync(1500);

    expect(session.conflict).toBe(true);
    expect(session.saveState).toBe("conflict");
    rename(session, "About us");
    await vi.advanceTimersByTimeAsync(1500);
    expect(api.save).toHaveBeenCalledTimes(1);

    await session.load();
    expect(session.conflict).toBe(false);
    expect(session.model!.screens[0].props.title).toBe("Your details");
  });

  it("says it couldn't save and waits for Retry", async () => {
    const { session, api } = await opened();
    api.save.mockRejectedValueOnce(new Error("offline"));
    rename(session, "About you");
    await vi.advanceTimersByTimeAsync(1500);

    expect(session.saveState).toBe("failed");
    expect(session.dirty).toBe(true);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(api.save).toHaveBeenCalledTimes(1);

    await session.save();
    expect(session.saveState).toBe("saved");
  });

  it("resumes after a failure on the next edit", async () => {
    const { session, api } = await opened();
    api.save.mockRejectedValueOnce(new Error("offline"));
    rename(session, "About you");
    await vi.advanceTimersByTimeAsync(1500);
    rename(session, "About us");
    expect(session.saveState).toBe("failed");

    await vi.advanceTimersByTimeAsync(1500);

    expect(api.save).toHaveBeenCalledTimes(2);
    expect(session.saveState).toBe("saved");
  });

  it("shows Meta's validation errors as problems on the uploaded blocks", async () => {
    const { session, api } = await opened();
    const added = addBlock(session.model!, session.model!.screens[0].uid, "TextBody", { text: "Hi" });
    session.apply(added.model);
    api.save.mockResolvedValueOnce({
      status: "Draft",
      modified: "m2",
      validation_errors: [
        { error: "INVALID_PROPERTY_VALUE", message: "Too long", pointers: [{ path: "screens[0].layout.children[3]" }] },
      ],
    });
    await vi.advanceTimersByTimeAsync(1500);

    expect(session.saveState).toBe("saved");
    expect(session.problems).toMatchObject([{ code: "INVALID_PROPERTY_VALUE", blockId: added.uid }]);
    expect(session.publishBlocker).toEqual({ reason: "errors", count: 1 });
    session.selectProblem(session.problems[0]);
    expect(session.selection.block).toBe(added.uid);
  });

  it("lists rule errors before warnings, Meta's first", async () => {
    const { session } = await opened();
    const block = session.model!.screens[0].blocks[0].uid;
    session.apply(updateBlock(session.model!, block, { text: "" }));
    session.checkRules();

    expect(session.problems.map((p) => p.code)).toEqual(["empty-text"]);
    expect(session.publishBlocker).toEqual({ reason: "errors", count: 1 });
  });
});

describe("flush", () => {
  it("saves a pending change at once", async () => {
    const { session, api } = await opened();
    rename(session, "About you");

    expect(await session.flush()).toBe(true);
    expect(api.save).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(5000);
    expect(api.save).toHaveBeenCalledTimes(1);
  });

  it("waits for the running save and saves what came after it", async () => {
    const { session, api } = await opened();
    const held = holdSaves(api);
    rename(session, "About you");
    await vi.advanceTimersByTimeAsync(1500);
    rename(session, "About us");
    const flushed = session.flush();
    await held.release();
    await held.release();

    expect(await flushed).toBe(true);
    expect(api.save.mock.calls[1][1]).toBe(JSON.stringify(serialize(session.model!)));
  });

  it("is false when the change can't be saved", async () => {
    const { session, api } = await opened();
    api.save.mockRejectedValueOnce(new Error("offline"));
    rename(session, "About you");

    expect(await session.flush()).toBe(false);
    expect(session.saveState).toBe("failed");
  });

  it("is false after a change made elsewhere", async () => {
    const { session, api } = await opened();
    api.touch();
    rename(session, "About you");

    expect(await session.flush()).toBe(false);
  });

  it("does nothing when everything is saved, or the Flow is read only", async () => {
    const saved = await opened();
    expect(await saved.session.flush()).toBe(true);

    const published = await opened(fakeApi(serverFlow({ status: "Published" })));
    expect(await published.session.flush()).toBe(true);

    expect(saved.api.save).not.toHaveBeenCalled();
    expect(published.api.save).not.toHaveBeenCalled();
  });
});

describe("publishing", () => {
  it("takes the new status, which makes the builder read only", async () => {
    const { session } = await opened();
    await session.publish();

    expect(session.flow!.status).toBe("Published");
    expect(session.readOnly).toBe(true);
  });
});

describe("the JSON tab", () => {
  it("applies valid JSON and keeps the selected screen's place", async () => {
    const { session } = await opened();
    session.select(session.model!.screens[1].uid);
    const json = JSON.parse(session.printed!.text);
    json.screens[1].title = "Money";

    expect(session.applyJson(JSON.stringify(json))).toBeNull();
    expect(session.model!.screens[1].props.title).toBe("Money");
    expect(session.selection.screen).toBe(session.model!.screens[1].uid);
    expect(session.dirty).toBe(true);
  });

  it("returns the line of a parse error and changes nothing", async () => {
    const { session } = await opened();
    const before = session.model;

    const error = session.applyJson('{\n  "version": "7.3",\n  "screens": [\n}');

    expect(error?.line).toBe(4);
    expect(session.model).toBe(before);
  });

  it("leaves an unchanged text alone", async () => {
    const { session } = await opened();
    const before = session.model;
    session.applyJson(session.printed!.text);

    expect(session.model).toBe(before);
  });
});

describe("the Flows list", () => {
  it("creates a blank Flow or a copy through create_flow, then reloads", async () => {
    const api = {
      list: vi.fn(async () => []),
      create: vi.fn(async () => "1300"),
    };
    const list = new FlowListSession(api as unknown as FlowBuilderApi, "Sales Line");
    const args = { account: "Sales Line", flow_name: "Copy", categories: ["OTHER" as const], clone_from: "1200" };

    expect(await list.create(args)).toBe("1300");
    expect(api.create).toHaveBeenCalledWith(args);
    expect(api.list).toHaveBeenCalledWith("Sales Line");
  });

  it("puts the server's name and category errors on their fields", () => {
    expect(fieldOfError({ exc_type: "FlowNameError" })).toBe("flow_name");
    expect(fieldOfError({ exc_type: "FlowCategoriesError" })).toBe("categories");
    expect(fieldOfError({ exc_type: "ValidationError" })).toBeNull();
  });
});
