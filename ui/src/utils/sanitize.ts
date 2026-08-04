import DOMPurify from "dompurify";
import type { Config } from "dompurify";

/**
 * DOMPurify options forwarded to {@link sanitizeHTML}.
 *
 * `RETURN_DOM` / `RETURN_DOM_FRAGMENT` are excluded: they make DOMPurify return a `Node`
 * rather than a string, and every caller here binds the result with `v-html`.
 */
export type SanitizeOptions = Omit<
  Config,
  "RETURN_DOM" | "RETURN_DOM_FRAGMENT"
>;

/**
 * Sanitize an HTML string for safe binding via `v-html`.
 *
 * WhatsApp message bodies are author-controlled text that we convert to HTML ourselves
 * (see `formatWhatsAppMessage`), and template bodies interpolate document-field values
 * server-side — either can carry markup such as `<img src=x onerror="...">`. DOMPurify keeps
 * benign formatting (`<b>`, `<i>`, links, …) while stripping scripts and event-handler
 * attributes, so the markup renders without executing.
 */
export function sanitizeHTML(
  html?: string | null,
  options?: SanitizeOptions
): string {
  if (!html) return "";
  return DOMPurify.sanitize(html, options ?? {});
}
