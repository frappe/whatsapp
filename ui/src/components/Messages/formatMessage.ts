import { sanitizeHTML } from "../../utils/sanitize";

/**
 * Convert WhatsApp's message markup to HTML, then sanitize it.
 *
 * Supported syntax:
 * - `_italic_`, `*bold*`, `~strikethrough~`
 * - ```` ```monospace``` ```` and `` `inline code` ``
 * - `> quote` at the start of a line
 * - `* item` / `- item` / `1. item` at the start of a line
 * - newlines become `<br>`
 *
 * Ordering matters: the block-level patterns are anchored to line starts (`^…$` with `/gm`)
 * so that digits and punctuation *mid-sentence* aren't mistaken for list items, which means
 * they must run before `\n` is replaced with `<br>` — once the newlines are gone, `^` only
 * matches the start of the whole string. Do not reorder or "simplify" these regexes.
 */
export function formatWhatsAppMessage(message?: string | null): string {
  if (!message) return "";
  let html = message;
  // if message contains _text_, make it italic
  html = html.replace(/_(.*?)_/g, "<i>$1</i>");
  // if message contains *text*, make it bold
  html = html.replace(/\*(.*?)\*/g, "<b>$1</b>");
  // if message contains ~text~, make it strikethrough
  html = html.replace(/~(.*?)~/g, "<s>$1</s>");
  // if message contains ```text```, make it monospace
  html = html.replace(/```(.*?)```/g, "<code>$1</code>");
  // if message contains `text`, make it inline code
  html = html.replace(/`(.*?)`/g, "<code>$1</code>");
  // Block-level patterns anchor to line starts so digits/punctuation mid-sentence
  // aren't mistaken for numbered-list items. Run before \n → <br> so ^ still works.
  html = html.replace(/^> (.*)$/gm, "<blockquote>$1</blockquote>");
  html = html.replace(/^[*-] (.+)$/gm, "<li>$1</li>");
  html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");
  html = html.replace(/\n/g, "<br>");

  return sanitizeHTML(html);
}
