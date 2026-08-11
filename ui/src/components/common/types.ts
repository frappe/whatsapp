import type { MediaFile, MediaKind } from "../../types";

/**
 * Caption-before-send dialog for an uploaded file. Sends on ctrl/cmd+enter, matching the
 * composer — a bare enter breaks the line in both.
 *
 * Emits: `send` (`caption: string`), `update:open` (`boolean`) for `v-model:open`.
 */
export interface MediaPreviewDialogProps {
  open: boolean;
  file?: MediaFile;
  /** picks the preview: image, video, or the generic document row */
  type?: MediaKind;
  loading?: boolean;
  /** defaults by `type`: "Send an image" / "Send a video" / "Send a file" */
  title?: string;
  /** default "Add a caption..." */
  captionPlaceholder?: string;
  /** default "Cancel" */
  cancelLabel?: string;
  /** default "Send" */
  sendLabel?: string;
}

/**
 * Fixed emoji bar shown on hover. There is no emoji search or picker by design.
 *
 * Emits: `select` (`emoji: string`).
 */
export interface ReactionPickerProps {
  /** default `["👍", "❤️", "😂", "😮", "😢", "🙏"]` */
  emojis?: string[];
}
