import { formatBytes } from "frappe-ui";
import type { MediaKind } from "../types";

/** MIME prefixes that map to a dedicated renderer. Everything else is a document. */
const MIME_CONTENT_TYPE_MAP: Record<string, MediaKind> = {
  "image/": "image",
  "audio/": "audio",
  "video/": "video",
};

/** Structural, so `WhatsAppMessage` satisfies it without `utils` importing `components`. */
export interface MediaAttachment {
  media_url?: string;
  file_name?: string;
  file_size?: number;
}

/** Pick the render kind for a message from its media's MIME type. */
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

/** Legacy rows store the file URL back in `message`, which is not a caption. */
export function hasCaption(caption?: string): boolean {
  return Boolean(caption && !caption.startsWith("/files/"));
}
