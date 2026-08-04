import { formatBytes } from "frappe-ui";
import type { MediaKind } from "../types";

/** MIME prefixes that map to a dedicated renderer. Everything else is a document. */
const MIME_CONTENT_TYPE_MAP: Record<string, MediaKind> = {
  "image/": "image",
  "audio/": "audio",
  "video/": "video",
};

/**
 * The attachment fields these helpers read. Structural, so any richer type carrying the same
 * field names — `WhatsAppMessage` above all — satisfies it with no conversion, and `utils`
 * still owes `components` nothing.
 */
export interface MediaAttachment {
  media_url?: string;
  file_name?: string;
  file_size?: number;
}

/**
 * Pick the render kind for a message from its media's MIME type.
 *
 * This derivation used to live server-side (CRM's `_infer_content_type`, which rewrote
 * `mime_type` into a `content_type` field before the UI ever saw it). It belongs here: the
 * message now carries the native `mime_type` and the UI decides how to draw it, so the
 * server-side helper becomes deletable once its host is wired to this package.
 */
export function contentTypeFromMime(mimeType?: string): MediaKind {
  if (!mimeType) return "text";
  const mime = mimeType.toLowerCase();
  for (const [prefix, contentType] of Object.entries(MIME_CONTENT_TYPE_MAP)) {
    if (mime.startsWith(prefix)) return contentType;
  }
  return "document";
}

/** Filename to show for an attachment, falling back to the media URL's basename. */
export function documentName(
  attachment: MediaAttachment,
  fallback = "Document"
): string {
  if (attachment.file_name) return attachment.file_name;
  // Fall back to the URL basename for media not backed by a local File record.
  const basename = (attachment.media_url || "").split("/").pop()?.split("?")[0];
  return basename || fallback;
}

/** Secondary line under an attachment's name, e.g. "PDF · 1.2 MB". Empty when neither is known. */
export function documentMeta(attachment: MediaAttachment): string {
  const name = documentName(attachment);
  const ext = name.includes(".")
    ? (name.split(".").pop() as string).toUpperCase()
    : "";
  const size = attachment.file_size ? formatBytes(attachment.file_size) : "";
  return [ext, size].filter(Boolean).join(" · ");
}

/**
 * Whether a media message's body is a caption worth rendering below the media.
 *
 * Media stores its caption in `message`, which is empty when there is none — or, on legacy
 * rows, the file URL repeated back.
 */
export function hasCaption(caption?: string): boolean {
  return Boolean(caption && !caption.startsWith("/files/"));
}
