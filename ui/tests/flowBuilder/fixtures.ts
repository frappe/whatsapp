import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { JsonObject } from "../../src/components/FlowBuilder/model";

/** Shared with the Python tests, which run the Flow outline on the same files. */
export const FLOW_JSON_DIR = join(__dirname, "../../../whatsapp/whatsapp/flows/flow_json");

export function flowJson(group: "meta" | "ours" | "builder", name: string): JsonObject {
  return JSON.parse(readFileSync(join(FLOW_JSON_DIR, group, `${name}.json`), "utf8"));
}

export function flowJsonNames(group: "meta" | "ours" | "builder"): string[] {
  return readdirSync(join(FLOW_JSON_DIR, group))
    .filter((file) => file.endsWith(".json"))
    .map((file) => file.slice(0, -".json".length));
}
