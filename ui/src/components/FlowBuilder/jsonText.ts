import type { JsonObject } from "./model";

export interface JsonError {
  message: string;
  line: number;
}

/** The parsed object, or where the text stops being a JSON object. */
export function readJson(text: string): { json: JsonObject } | { error: JsonError } {
  try {
    const json = JSON.parse(text);
    if (json && typeof json === "object" && !Array.isArray(json)) return { json };
    return { error: { message: "Flow JSON must be an object.", line: 1 } };
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return { error: { message, line: errorLine(text, message) } };
  }
}

/** Engines name the line, or only the character position, in their message. */
function errorLine(text: string, message: string): number {
  const line = /line (\d+)/.exec(message);
  if (line) return Number(line[1]);
  const position = /position (\d+)/.exec(message);
  if (!position) return text.split("\n").length;
  return text.slice(0, Number(position[1])).split("\n").length;
}
