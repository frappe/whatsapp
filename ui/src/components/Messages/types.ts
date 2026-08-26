/**
 * The `@whatsapp/ui` messages contract: what
 * `whatsapp.whatsapp.api.messages.get_messages` returns, under the DocType's own fieldnames.
 */

import type { MaybeRefOrGetter } from "vue";
import type { MediaFile, MediaKind } from "../../types";

export type { MediaFile };

/** "Outgoing" = sent by the agent, "Incoming" = by the contact. */
export type WhatsAppDirection = "Incoming" | "Outgoing";

/**
 * Title Case exactly as stored — never lowercase it. `Pending` is the initial state and
 * renders no delivery tick.
 */
export type WhatsAppStatus =
  | "Pending"
  | "Sent"
  | "Delivered"
  | "Read"
  | "Failed";

/** Derived from `mime_type` by `contentTypeFromMime()`; never stored, never overridable. */
export type WhatsAppContentType = MediaKind;

/**
 * One participant's reaction, folded onto its target by `get_messages`. Each side keeps at
 * most one, so a message has 0–2.
 */
export interface WhatsAppReaction {
  emoji: string;
  direction: WhatsAppDirection;
}

/** Serves both a sent message's rendered buttons and an unsent template's preview. */
export interface WhatsAppTemplateButton {
  button_type:
    | "Quick Reply"
    | "URL"
    | "Copy Code"
    | "Phone Number"
    | "Voice Call";
  button_text: string;
  url?: string;
  phone_number?: string;
}

/**
 * A single message in the conversation. Which group a field is in tells you where to look
 * when it is wrong: a column, or something `get_messages` computed.
 */
export interface WhatsAppMessage {
  // —— `WhatsApp Message` DocType fields ——
  /** docname; also the DOM id a reply quote scrolls to */
  name: string;
  direction: WhatsAppDirection;
  creation: string;
  /** body text, or the caption of a media message */
  message?: string;
  status?: WhatsAppStatus;
  /** recipient's WhatsApp Profile; empty on incoming messages */
  to?: string;
  /** sender's phone number; empty on outgoing messages */
  from?: string;
  mime_type?: string;
  media_url?: string;
  is_template?: boolean;
  /** link to the `WhatsApp Template` used, when `is_template` */
  whatsapp_template?: string;
  /** WhatsApp's own message id; what `context_message_id` and reactions point at */
  message_id?: string;
  /** the `message_id` this message replies to (or reacts to) */
  context_message_id?: string;
  reference_doctype?: string;
  reference_docname?: string;
  /** JSON string of the variables used to render the template body */
  template_body_parameters?: string;
  /** JSON string of the variables used to render the template header */
  template_header_parameters?: string;
  /** set only on reaction rows; folded away into {@link reactions} by `get_messages` */
  reaction?: string;
  error_message?: string;

  // —— server-derived ——
  reactions?: WhatsAppReaction[];
  /** `File.file_name` for `media_url`; falls back to the URL basename when absent */
  file_name?: string;
  /** `File.file_size` in bytes */
  file_size?: number;
  /** body of the message this one replies to, quoted above the bubble */
  reply_message?: string;
  /** docname of the replied-to message — the scroll target for the quote block */
  reply_to?: string;
  reply_to_direction?: WhatsAppDirection;
  /** rendered template body, variables already substituted; shown when `is_template` */
  template?: string;
  /** rendered template header text */
  header?: string;
  footer?: string;
  buttons?: WhatsAppTemplateButton[];
  template_name?: string;
}

/** Exactly what `get_sendable_templates` returns, buttons included. */
export interface WhatsAppTemplate {
  name: string;
  /** template body, may contain unresolved `{{ variables }}` */
  message?: string;
  footer?: string;
  header_text?: string;
  header_type?: "Text" | "Image" | "Document" | "GIF" | "Video";
  /** DocType the template is bound to; empty for unbound templates */
  reference_doctype?: string;
  /** child table, so it needs its own query — optional for a host supplying its own list */
  buttons?: WhatsAppTemplateButton[];
}

// —— outbound payloads ——

/**
 * Assembled by {@link MessagesController.buildPayload}. Carries no `to` or reference: those
 * are conversation scope, supplied once as {@link UseMessagesOptions}.
 */
export interface SendMessagePayload {
  /** typed body, or the caption when `attach` is set; may be empty for a bare attachment */
  message: string;
  /** `file_url` of the uploaded media */
  attach?: string;
  contentType: WhatsAppContentType;
  /** docname of the message being replied to */
  replyTo?: string;
}

/** Emitted as `react` when a reaction is picked. */
export interface ReactPayload {
  messageName: string;
  emoji: string;
}

// —— component props ——

/**
 * The conversation. Layout-neutral — no scroll container, no padding — and inherits attrs.
 * Messages run flat in send order; the only structure imposed is a rule between calendar days.
 *
 * Emits: `reply` ({@link WhatsAppMessage} — hand it to `setReplyTo`), `react` ({@link ReactPayload}).
 * Slots: `avatar` (`{ message }`) — renders nothing, and reserves no width, unless supplied.
 */
export interface MessageListProps {
  /** oldest first, as {@link MessagesController.messages} holds them */
  messages: WhatsAppMessage[];
  /** first-load spinner; only meaningful while `messages` is empty */
  loading?: boolean;
  /**
   * last failure, as {@link MessagesController.error} holds it. Shown instead of the empty
   * state while there are no messages, so a failed fetch cannot read as an empty conversation.
   */
  error?: unknown;
  /** applied to every message row, for a host that needs to find rows in the DOM */
  rowClass?: string;

  // — chrome (English defaults; override to translate) —
  /** default "Contact" — the other participant, named on every incoming bubble */
  senderName?: string;
  /** default "You" */
  youLabel?: string;
  /** default "Reacted by" */
  reactedByLabel?: string;
  /** default "Reply" */
  replyLabel?: string;
  /** default "Replying to" — prefixes the sender named in a bubble's reply quote */
  replyingToLabel?: string;
  /** default "Failed to send message" */
  failedMessageLabel?: string;
  /** default "React" — accessible name of the reaction trigger */
  reactLabel?: string;
  /** default "No messages yet" */
  emptyLabel?: string;
  /** default "Messages sent to and from this contact will appear here." — pass "" to omit */
  emptyDescription?: string;
  /** default "Could not load messages" — shown when {@link error} is set and there are none */
  errorLabel?: string;
  /** default "Today" — day separator label for the current day */
  todayLabel?: string;
  /** default "Yesterday" */
  yesterdayLabel?: string;
  /** default `["👍", "❤️", "😂", "😮", "😢", "🙏"]` */
  reactionEmojis?: string[];
}

/**
 * One bubble: the coloured body, plus the footer below it carrying the time, the delivery
 * tick and the reply action. Picks its body renderer from the message's content type.
 *
 * Emits: `reply` ({@link WhatsAppMessage}), `jump-to` (`name: string`) — the list owns the scroll.
 * Slots: `actions` — rendered beside the coloured body, next to the built-in reply button and
 * vertically centred on the bubble. The bubble owns the hover/focus reveal and the `Failed`
 * guard for the whole pair, so slot content needs neither.
 */
export interface MessageBubbleProps {
  message: WhatsAppMessage;
  /** default "Contact" — used for anything `Incoming`; `youLabel` covers `Outgoing` */
  senderName?: string;
  /** default "You" */
  youLabel?: string;
  /** default "Reacted by" */
  reactedByLabel?: string;
  /** default "Reply" */
  replyLabel?: string;
  /** default "Replying to" — prefixes the sender named in the reply quote */
  replyingToLabel?: string;
  /** default "Failed to send message" */
  failedMessageLabel?: string;
}

/**
 * The button row under a template's body. Renders nothing when there are no buttons, and is
 * display only — what WhatsApp will show on the recipient's phone, so no clicks and no emit.
 */
export interface TemplateButtonsProps {
  buttons?: WhatsAppTemplateButton[];
}

// —— the messages controller ——

/** A `[doctype, docname]` pair naming a document messages hang off. */
export type MessageReference = [doctype: string, docname: string];

/** Options for `useMessages()`. Each may be a plain value, a ref, or a getter. */
export interface UseMessagesOptions {
  /** the conversation's scope; **the first pair is where a send attaches** */
  references: MaybeRefOrGetter<MessageReference[]>;
  /** recipient — a `WhatsApp Profile` name or a phone number; required to send */
  to: MaybeRefOrGetter<string | undefined>;
  initialDraft?: string;
}

/**
 * The controller returned by `useMessages()`. A `reactive` proxy — spread it with
 * `v-bind="messages"` and read members directly; destructuring drops reactivity.
 */
export interface MessagesController {
  /** the conversation, oldest first across every reference */
  messages: WhatsAppMessage[];
  /** a fetch is in flight; pair with `messages.length` for a first-load-only spinner */
  loading: boolean;
  /** a send is in flight. `canSend` already accounts for it — this is for showing progress */
  sending: boolean;
  /** last failure of a fetch, a send or a reaction; `null` while healthy. Verbs never throw */
  error: unknown;
  reload: () => Promise<void>;
  /**
   * Returns the new message's docname, or `null` when there was nothing to send, no
   * recipient, or the call failed. A media send keeps the draft; a text send clears it.
   */
  send: (
    overrides?: Pick<SendMessagePayload, "message">
  ) => Promise<string | null>;
  /** returns the reaction message's docname, or `null` on failure */
  react: (messageName: string, emoji: string) => Promise<string | null>;

  // — composing —
  /** the text being typed; also the caption of a media send */
  draft: string;
  /** the upload staged by `attach()`, awaiting a send */
  pendingMedia?: MediaFile;
  /** render kind of {@link pendingMedia}; "document" when nothing is staged */
  pendingType: WhatsAppContentType;
  replyTo: WhatsAppMessage | null;
  /** whether `buildPayload()` would return a payload rather than `null` */
  canSend: boolean;
  /** write the draft — the path for a UI bound by `v-bind`, which sees `draft` read-only */
  setDraft: (text: string) => void;
  setReplyTo: (message: WhatsAppMessage) => void;
  clearReply: () => void;
  /** stage an upload; `type` picks its preview and the outgoing content type */
  attach: (file: MediaFile, type?: WhatsAppContentType) => void;
  clearAttachment: () => void;
  /**
   * What `send()` would send, or `null` when there is nothing to. `overrides.message`
   * supplies a body from outside the draft, e.g. a caption typed in the preview dialog.
   */
  buildPayload: (
    overrides?: Pick<SendMessagePayload, "message">
  ) => SendMessagePayload | null;
  /** clear the draft, the attachment and the reply */
  reset: () => void;
}

// —— the templates controller ——

/** Options for `useTemplates()`. Each may be a plain value, a ref, or a getter. */
export interface UseTemplatesOptions {
  /** decides which templates are offered: those bound to it, plus unbound ones with no variables */
  referenceDoctype: MaybeRefOrGetter<string | undefined>;
  /** document a sent template attaches to */
  referenceDocname?: MaybeRefOrGetter<string | undefined>;
  /** recipient — a `WhatsApp Profile` name or a phone number; required to send */
  to?: MaybeRefOrGetter<string | undefined>;
}

/** Per-call overrides for {@link TemplatesController.sendTemplate}. */
export interface SendTemplateOverrides {
  to?: string;
  referenceDocname?: string;
}

/**
 * The controller returned by `useTemplates()`. Kept apart from {@link MessagesController}
 * because a template send composes nothing — the body is rendered server-side.
 */
export interface TemplatesController {
  /** Approved templates sendable from `referenceDoctype`, buttons included */
  templates: WhatsAppTemplate[];
  loading: boolean;
  /** last failure of the fetch or either write; `null` while healthy. Verbs never throw */
  error: unknown;
  reload: () => Promise<void>;
  /** returns the new message's docname, or `null` on failure */
  sendTemplate: (
    templateName: string,
    overrides?: SendTemplateOverrides
  ) => Promise<string | null>;
  /**
   * Create a `WhatsApp Template`, push it to Meta and refresh the list. It will not appear
   * in `templates` until Meta approves it.
   */
  createTemplate: (
    template: Record<string, unknown>,
    accountName: string
  ) => Promise<Record<string, unknown> | null>;
}

/**
 * The default input area. Holds no composing state of its own — it reads and writes the
 * controller spread onto it with `v-bind="messages"`.
 *
 * The reply preview sits inside the composer's border, above the field. Draws no page padding
 * of its own; a host supplies it, and a `class` lands on the root above the composer.
 * Accepts a dropped or pasted file as well as a picked one. Sending is ctrl/cmd+enter,
 * leaving a bare enter to break the line.
 *
 * Emits: `send` ({@link SendMessagePayload}) **after** the send lands, as a notification.
 * Slots: `leading-actions` — rendered at the start of the action row, inside the composer.
 * Exposes: `focus()`.
 */
export interface MessageInputProps {
  /** default "Type your message here..." */
  placeholder?: string;
  /** default "Contact" — names an incoming message in the reply preview */
  senderName?: string;
  /** default "You" */
  youLabel?: string;
  /** default "Upload Document" */
  uploadDocumentLabel?: string;
  /** default "Upload Image" */
  uploadImageLabel?: string;
  /** default "Upload Video" */
  uploadVideoLabel?: string;
  /** default "Add a caption..." — forwarded to the media preview dialog */
  captionPlaceholder?: string;
  /** default "Replying to" — prefixes the quoted message's sender in the reply preview */
  replyingToLabel?: string;
  /** default "Dismiss reply" — accessible name of the reply preview's close button */
  dismissReplyLabel?: string;
  /**
   * default "Send". The send button is icon-only, so this is its tooltip and its accessible
   * name. Do not append the keyboard hint — the tooltip renders it, and which modifier to
   * name is detected from the platform.
   */
  sendLabel?: string;
  disabled?: boolean;
}

/**
 * One template's body, rendered. Serves both ends of a template's life — a sent
 * {@link WhatsAppMessage}'s `header`/`template`/`footer` and an unsent
 * {@link WhatsAppTemplate}'s `header_text`/`message`/`footer` — so a preview cannot drift
 * from the bubble it becomes.
 */
export interface TemplateContentProps {
  /** `WhatsAppMessage.header` or `WhatsAppTemplate.header_text` */
  header?: string;
  /** `WhatsAppMessage.template` (substituted) or `WhatsAppTemplate.message` (raw) */
  body?: string;
  footer?: string;
  buttons?: WhatsAppTemplateButton[];
  /** class for the body element only, so a fixed-height card can scroll just the body */
  bodyClass?: string;
}
