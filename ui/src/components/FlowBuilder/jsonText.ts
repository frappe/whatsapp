import type { Json, JsonObject } from "./model";

export interface PrintedJson {
  /** Same text as `JSON.stringify(value, null, 2)`. */
  text: string;
  /** The line each path starts on, e.g. `screens[0].layout.children[1]` → 14. */
  lines: Map<string, number>;
}

export interface JsonError {
  message: string;
  line: number;
}

export function printJson(value: Json): PrintedJson {
  const printer = new Printer();
  printer.value(value, "", "");
  return { text: printer.text, lines: printer.lines };
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

class Printer {
  text = "";
  lines = new Map<string, number>();
  private line = 1;

  value(value: Json, path: string, indent: string) {
    if (Array.isArray(value)) this.array(value, path, indent);
    else if (value && typeof value === "object") this.object(value, path, indent);
    else this.write(JSON.stringify(value));
  }

  private array(items: Json[], path: string, indent: string) {
    if (!items.length) return this.write("[]");
    const inner = indent + "  ";
    this.write("[\n");
    items.forEach((item, index) => {
      this.write(inner);
      this.lines.set(`${path}[${index}]`, this.line);
      this.value(item, `${path}[${index}]`, inner);
      this.write(index < items.length - 1 ? ",\n" : "\n");
    });
    this.write(`${indent}]`);
  }

  private object(object: JsonObject, path: string, indent: string) {
    const entries = Object.entries(object).filter(([, item]) => item !== undefined);
    if (!entries.length) return this.write("{}");
    const inner = indent + "  ";
    this.write("{\n");
    entries.forEach(([key, item], index) => {
      const child = path ? `${path}.${key}` : key;
      this.lines.set(child, this.line);
      this.write(`${inner}${JSON.stringify(key)}: `);
      this.value(item, child, inner);
      this.write(index < entries.length - 1 ? ",\n" : "\n");
    });
    this.write(`${indent}}`);
  }

  private write(text: string) {
    this.text += text;
    for (const char of text) if (char === "\n") this.line++;
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
