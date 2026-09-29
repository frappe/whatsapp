const VARIABLE = /\{\{\s*(\w+)\s*\}\}/g;

/** Every distinct `{{name}}` across the texts, in first-seen order. */
export function variableNames(...texts: (string | undefined)[]): string[] {
  const names = texts.flatMap((text) => [...(text ?? "").matchAll(VARIABLE)].map((m) => m[1]));
  return [...new Set(names)];
}

/** The text with each `{{name}}` replaced by its example; a name with no example stays as typed. */
export function fillVariables(text: string | undefined, examples: Map<string, string>): string {
  return (text ?? "").replace(VARIABLE, (match, name: string) => examples.get(name) || match);
}
