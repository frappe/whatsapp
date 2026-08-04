/**
 * Types shared across the package, in no one component's ownership.
 *
 * Kept at the root so `utils/` can use them without importing from `components/` — that
 * direction has to stay one-way.
 */

/**
 * How a media body should be rendered.
 *
 * Derived from a MIME type by `contentTypeFromMime()` in `./utils/media`, never stored: an
 * `image/`, `audio/` or `video/` prefix picks that kind, any other MIME type is a `document`,
 * and no MIME type at all means plain `text`.
 */
export type MediaKind = "text" | "image" | "audio" | "video" | "document";

/** An uploaded file, as frappe-ui's `FileUploader` reports it on success. */
export interface MediaFile {
  file_url: string;
  file_name?: string;
  file_size?: number;
}
