import DOMPurify from "dompurify";
import type { Config } from "dompurify";

/** `RETURN_DOM*` is excluded: it returns a `Node`, and every caller binds a string. */
export type SanitizeOptions = Omit<
  Config,
  "RETURN_DOM" | "RETURN_DOM_FRAGMENT"
>;

/**
 * Sanitize an HTML string for safe binding via `v-html`. Message and template bodies carry
 * sender- and field-supplied text, so either can arrive as `<img src=x onerror="…">`.
 */
export function sanitizeHTML(
  html?: string | null,
  options?: SanitizeOptions
): string {
  if (!html) return "";
  return DOMPurify.sanitize(html, options ?? {});
}
