/**
 * Types shared across the package. Kept at the root so `utils/` can use them without
 * importing from `components/` — that direction has to stay one-way.
 */

/** Derived from a MIME type by `contentTypeFromMime()` in `./utils/media`, never stored. */
export type MediaKind = "text" | "image" | "audio" | "video" | "document";

/** An uploaded file, as frappe-ui's `FileUploader` reports it on success. */
export interface MediaFile {
  file_url: string;
  file_name?: string;
  file_size?: number;
}
