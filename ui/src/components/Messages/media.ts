import { formatBytes } from "frappe-ui";
import type { WhatsAppContentType, WhatsAppMessage } from "./types";

/** MIME prefixes that map to a dedicated renderer. Everything else is a document. */
const MIME_CONTENT_TYPE_MAP: Record<string, WhatsAppContentType> = {
  "image/": "image",
  "audio/": "audio",
  "video/": "video",
};

/**
 * Pick the render kind for a message from its media's MIME type.
 *
 * This derivation used to live server-side (CRM's `_infer_content_type`, which rewrote
 * `mime_type` into a `content_type` field before the UI ever saw it). It belongs here: the
 * message now carries the native `mime_type` and the UI decides how to draw it, so the
 * server-side helper becomes deletable once its host is wired to this package.
 */
export function contentTypeFromMime(mimeType?: string): WhatsAppContentType {
  if (!mimeType) return "text";
  const mime = mimeType.toLowerCase();
  for (const [prefix, contentType] of Object.entries(MIME_CONTENT_TYPE_MAP)) {
    if (mime.startsWith(prefix)) return contentType;
  }
  return "document";
}

/** Filename to show for an attachment, falling back to the media URL's basename. */
export function documentName(
  message: WhatsAppMessage,
  fallback = "Document"
): string {
  if (message.file_name) return message.file_name;
  // Fall back to the URL basename for media not backed by a local File record.
  const basename = (message.media_url || "").split("/").pop()?.split("?")[0];
  return basename || fallback;
}

/** Secondary line under an attachment's name, e.g. "PDF · 1.2 MB". Empty when neither is known. */
export function documentMeta(message: WhatsAppMessage): string {
  const name = documentName(message);
  const ext = name.includes(".")
    ? (name.split(".").pop() as string).toUpperCase()
    : "";
  const size = message.file_size ? formatBytes(message.file_size) : "";
  return [ext, size].filter(Boolean).join(" · ");
}

/** Whether a media message has a caption to render below the media. */
export function hasCaption(message: WhatsAppMessage): boolean {
  // Media `message` is the caption; it's empty (or a legacy /files URL) when
  // there's no caption, in which case nothing should render below the media.
  return Boolean(message.message && !message.message.startsWith("/files/"));
}
