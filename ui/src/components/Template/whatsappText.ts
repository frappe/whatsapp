// WhatsApp text: `*bold*`, `_italic_`, `~strike~`, one line per newline, no nesting.

export interface JsonNode {
  type: string;
  text?: string;
  marks?: { type: string }[];
  content?: JsonNode[];
}

const MARK_FOR_DELIMITER: Record<string, string> = { "*": "bold", _: "italic", "~": "strike" };
const DELIMITER_FOR_MARK: Record<string, string> = { bold: "*", italic: "_", strike: "~" };

export function fromWhatsAppText(text: string | null | undefined): JsonNode {
  const lines = (text ?? "").split("\n");
  return {
    type: "doc",
    content: lines.map((line) => {
      const content = inlineNodes(line);
      return content.length ? { type: "paragraph", content } : { type: "paragraph" };
    }),
  };
}

export function toWhatsAppText(doc: JsonNode | null | undefined): string {
  return (doc?.content ?? []).map(paragraphText).join("\n");
}

function paragraphText(paragraph: JsonNode): string {
  return (paragraph.content ?? []).map(inlineText).join("");
}

function inlineText(node: JsonNode): string {
  if (node.type === "hardBreak") return "\n";
  let text = node.text ?? "";
  for (const mark of node.marks ?? []) {
    const delimiter = DELIMITER_FOR_MARK[mark.type];
    if (delimiter) text = `${delimiter}${text}${delimiter}`;
  }
  return text;
}

// A delimiter inside a word is text, as in `{{first_name}}`; `formatWhatsAppMessage` agrees.
function inlineNodes(line: string): JsonNode[] {
  const nodes: JsonNode[] = [];
  let plain = "";
  let i = 0;
  while (i < line.length) {
    const delimiter = line[i];
    const close = MARK_FOR_DELIMITER[delimiter] ? spanEnd(line, i) : -1;
    if (close !== -1) {
      if (plain) nodes.push({ type: "text", text: plain });
      plain = "";
      nodes.push({
        type: "text",
        text: line.slice(i + 1, close),
        marks: [{ type: MARK_FOR_DELIMITER[delimiter] }],
      });
      i = close + 1;
      continue;
    }
    plain += delimiter;
    i += 1;
  }
  if (plain) nodes.push({ type: "text", text: plain });
  return nodes;
}

function spanEnd(line: string, open: number): number {
  const isWord = (index: number) => index >= 0 && index < line.length && /\w/.test(line[index]);
  if (isWord(open - 1)) return -1;
  const close = line.indexOf(line[open], open + 1);
  if (close <= open + 1 || isWord(close + 1)) return -1;
  return close;
}
