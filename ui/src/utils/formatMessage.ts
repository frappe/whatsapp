import { sanitizeHTML } from "./sanitize";

/** Convert WhatsApp's message markup to HTML, then sanitize it. */
export function formatWhatsAppMessage(message?: string | null): string {
  if (!message) return "";
  let html = message;
  // `{1,2}` because WhatsApp accepts a doubled delimiter: against `__text__` a lazy `.*?`
  // matches empty between the two halves, emitting `<i></i>text<i></i>` — the markers are
  // deleted and nothing is styled. The word-boundary guards keep `snake_case` and the
  // underscores in a URL from being marked up.
  html = html.replace(/(?<!\w)_{1,2}([^\n]+?)_{1,2}(?!\w)/g, "<i>$1</i>");
  html = html.replace(/(?<!\w)\*{1,2}([^\n]+?)\*{1,2}(?!\w)/g, "<b>$1</b>");
  html = html.replace(/(?<!\w)~{1,2}([^\n]+?)~{1,2}(?!\w)/g, "<s>$1</s>");
  html = html.replace(/```(.*?)```/g, "<code>$1</code>");
  html = html.replace(/`(.*?)`/g, "<code>$1</code>");
  // Anchored to line starts so digits mid-sentence aren't matched as list items, which means
  // these must run before \n → <br>: after that, ^ only matches the start of the string.
  html = html.replace(/^> (.*)$/gm, "<blockquote>$1</blockquote>");
  html = html.replace(/^[*-] (.+)$/gm, "<li>$1</li>");
  html = html.replace(/^\d+\. (.+)$/gm, "<li>$1</li>");
  html = html.replace(/\n/g, "<br>");

  return sanitizeHTML(html);
}
