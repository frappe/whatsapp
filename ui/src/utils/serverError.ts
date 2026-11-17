import { WHATSAPP_DOCS_URL } from "./metaDocs";

// The server appends ` · <a …>` to a Meta error. Hosts sanitize HTML, which drops the link's
// `target`, so a click would leave the app: the text is shown without it and the link is
// rendered by the component instead (see `isMetaError`).
const DOCS_LINK = /\s*·\s*<a\s[^>]*>[^<]*<\/a>/g;

function rawServerText(error: unknown): string {
  if (!error) return "";
  const { messages, message } = error as { messages?: string[]; message?: string };
  return messages?.length ? messages.join("\n") : (message ?? String(error));
}

// A failed frappe-ui `call` carries the server's text on `messages`; `message` is only the method path.
export function serverErrorMessage(error: unknown): string {
  return rawServerText(error).replace(DOCS_LINK, "");
}

/** True when the server marked the error as Meta's, so it is worth linking the WhatsApp docs. */
export function isMetaError(error: unknown): boolean {
  return rawServerText(error).includes(WHATSAPP_DOCS_URL);
}
