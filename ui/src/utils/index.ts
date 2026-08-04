export { sanitizeHTML } from "./sanitize";
export type { SanitizeOptions } from "./sanitize";
export { formatWhatsAppMessage } from "./formatMessage";
// `contentTypeFromMime` settles the text/image/audio/video/document question that no stored
// column answers. The filename/size/caption helpers travel with it because a host rendering
// its own bubble needs the same fallbacks the bundled one uses.
export {
  contentTypeFromMime,
  documentMeta,
  documentName,
  hasCaption,
} from "./media";
export type { MediaAttachment } from "./media";
