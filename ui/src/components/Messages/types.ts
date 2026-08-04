/**
 * The `@whatsapp/ui` messages contract.
 *
 * Field names are the WhatsApp app's own (`WhatsApp Message` / `WhatsApp Template` DocType
 * fieldnames) — not any host's legacy dialect, and no host adapter maps them: they are what
 * `whatsapp.whatsapp.api.messages.get_messages` returns. The composables
 * ({@link MessagesController}, {@link TemplatesController}) own the fetching and the writing;
 * the components render what a controller holds and report interactions as events.
 */

import type { MaybeRefOrGetter } from "vue";
import type { MediaFile, MediaKind } from "../../types";

export type { MediaFile };

/** `WhatsApp Message.direction`. "Outgoing" = sent by the agent, "Incoming" = by the contact. */
export type WhatsAppDirection = "Incoming" | "Outgoing";

/**
 * `WhatsApp Message.status`, Title Case exactly as stored.
 *
 * `"Pending"` is the DocType's default, so it is the state every message starts in — an
 * outgoing message is Pending until the send call returns. It renders no delivery tick: the
 * single tick means Sent, the double tick means Delivered/Read, and Pending falls through to
 * nothing. That is the existing behaviour, not a gap.
 *
 * Do not lowercase these — normalizing case at the API boundary is the legacy behaviour this
 * package exists to stop.
 */
export type WhatsAppStatus =
  | "Pending"
  | "Sent"
  | "Delivered"
  | "Read"
  | "Failed";

/**
 * How a message body should be rendered.
 *
 * Always derived from the message's `mime_type` by `contentTypeFromMime()` in
 * `utils/media`. There is no stored column behind this and no way to override it — the MIME
 * type is the single source of truth.
 *
 * Inbound button and interactive replies are not a separate kind: the webhook stores the
 * button's text as the message body and sets no `mime_type`, so they derive to `"text"`,
 * which is how they have always rendered.
 */
export type WhatsAppContentType = MediaKind;

/**
 * One participant's reaction to a message.
 *
 * WhatsApp delivers reactions as separate message documents carrying `reaction` +
 * `context_message_id`; `get_messages` folds them onto their target. Each side keeps at most
 * one, so a message has 0–2 of these.
 *
 * There is no reactor name here, by design: who reacted is presentation, and the same rule
 * the bubble uses for a sender applies — `direction` picks between `youLabel` and
 * `senderName`.
 */
export interface WhatsAppReaction {
  emoji: string;
  /** which side reacted — same axis as {@link WhatsAppMessage.direction} */
  direction: WhatsAppDirection;
}

/**
 * One row of `WhatsApp Template.buttons`.
 *
 * The same shape serves both sides: the rendered buttons folded onto a sent message
 * ({@link WhatsAppMessage.buttons}) and the ones previewed on an unsent template
 * ({@link WhatsAppTemplate.buttons}). There is only ever this one shape — a preview that
 * disagreed with the bubble would be the bug the shared shape exists to prevent.
 */
export interface WhatsAppTemplateButton {
  button_type:
    | "QUICK_REPLY"
    | "URL"
    | "COPY_CODE"
    | "PHONE_NUMBER"
    | "VOICE_CALL";
  button_text: string;
  url?: string;
  phone_number?: string;
}

/**
 * A single message in the conversation.
 *
 * The fields split into two groups:
 *
 * 1. **DocType fields** — read straight off `WhatsApp Message`, unrenamed.
 * 2. **Server-derived fields** — exist in no table. `get_messages` computes them by resolving
 *    linked documents, folding reaction rows, joining `File` and rendering the template; they
 *    need server-side data the library cannot reach.
 *
 * Values the library derives itself, so neither group carries a column for them: "is this a
 * reply?" is `Boolean(message.context_message_id)`, and the render kind comes from
 * `contentTypeFromMime(message.mime_type)`. Who sent it is presentation and never travels on
 * the wire either — see the `senderName` prop on {@link MessageBubbleProps}.
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
  /** sender's phone number; empty on outgoing messages (they come from the agent) */
  from?: string;
  /** MIME type of `media_url`; absent on plain text messages */
  mime_type?: string;
  /** public URL of the attached media */
  media_url?: string;
  /** true when the body was sent from a `WhatsApp Template` rather than typed */
  is_template?: boolean;
  /** link to the `WhatsApp Template` used, when `is_template` */
  whatsapp_template?: string;
  /** WhatsApp's own message id; what `context_message_id` and reactions point at */
  message_id?: string;
  /** the `message_id` this message replies to (or reacts to) */
  context_message_id?: string;
  reference_doctype?: string;
  reference_docname?: string;
  /** JSON string of the body variables used to render the template */
  template_body_parameters?: string;
  /** JSON string of the header variables used to render the template */
  template_header_parameters?: string;
  /** set only on reaction rows; folded away into {@link reactions} by `get_messages` */
  reaction?: string;
  /** human-readable failure reason, shown when `status === "Failed"` */
  error_message?: string;

  // —— server-derived ——
  /** reactions folded onto this message from their own message rows */
  reactions?: WhatsAppReaction[];
  /** `File.file_name` for `media_url`; falls back to the URL basename when absent */
  file_name?: string;
  /** `File.file_size` in bytes */
  file_size?: number;
  /** body of the message this one replies to, quoted above the bubble */
  reply_message?: string;
  /** docname of the replied-to message — the scroll target for the quote block */
  reply_to?: string;
  /** direction of the replied-to message; colours the quote block's border and names its sender */
  reply_to_direction?: WhatsAppDirection;
  /** rendered template body, variables already substituted; shown when `is_template` */
  template?: string;
  /** rendered template header text */
  header?: string;
  /** template footer text */
  footer?: string;
  /** rendered template buttons */
  buttons?: WhatsAppTemplateButton[];
  /** `WhatsApp Template.template_name` of the template used */
  template_name?: string;
}

/**
 * A sendable template — the `WhatsApp Template` fields a host needs to offer one.
 *
 * Exactly what `get_sendable_templates` returns, buttons included. Feed `header_text`, the
 * body, `footer` and `buttons` to {@link TemplateContentProps} to preview what a send will
 * actually render, through the same component the sent bubble uses.
 */
export interface WhatsAppTemplate {
  /** docname; shown as the card title and emitted on select */
  name: string;
  /** template body, may contain unresolved `{{ variables }}` */
  message?: string;
  footer?: string;
  header_text?: string;
  header_type?: "TEXT" | "IMAGE" | "DOCUMENT" | "GIF" | "VIDEO";
  /** DocType the template is bound to; empty for unbound templates */
  reference_doctype?: string;
  /**
   * `WhatsApp Template.buttons`, a **child table** — fetched by its own query.
   *
   * A `frappe.get_all("WhatsApp Template", fields=[…])` cannot return one no matter what you
   * put in the field list; only `frappe.get_doc` or a second query against
   * `WhatsApp Template Button` (filtered by `parent` / `parenttype`) will.
   * `get_sendable_templates` does the second query, so these arrive filled. It stays optional
   * for a host supplying its own list: without buttons the picker still renders
   * header/body/footer, only less completely than the bubble that message becomes.
   */
  buttons?: WhatsAppTemplateButton[];
}

// —— outbound payloads ——

/**
 * Assembled by {@link MessagesController.buildPayload}, consumed by
 * {@link MessagesController.send}, and re-emitted as `send` by the input once the send
 * lands — a host listens to scroll to the bottom, not to perform the call.
 *
 * Deliberately carries no `to`, no `reference_doctype` and no `reference_docname`: those are
 * conversation scope, fixed for the life of the controller and supplied once as
 * {@link UseMessagesOptions}, not re-stated per message.
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

/** Emitted as `react` when a reaction is picked. `messageName` is the target's docname. */
export interface ReactPayload {
  messageName: string;
  emoji: string;
}

// —— component props ——

/**
 * The conversation: every bubble, its loading and empty states, and the scroll-to-message
 * behaviour behind reply quotes.
 *
 * Layout-neutral by design — no scroll container and no padding, because the host owns where
 * the conversation sits and how tall it is. It inherits attrs, so a `class` lands on the
 * list root.
 *
 * Emits: `reply` ({@link WhatsAppMessage} — hand it to `setReplyTo`), `react`
 * ({@link ReactPayload}).
 */
export interface MessageListProps {
  /** oldest first, as {@link MessagesController.messages} holds them */
  messages: WhatsAppMessage[];
  /** first-load spinner; only meaningful while `messages` is empty */
  loading?: boolean;
  /**
   * Class applied to every message row, for a host that needs to find rows in the DOM.
   *
   * CRM's `Activities.vue` collects `.activity` elements to position its scroll, and its
   * WhatsApp rows have to be among them — but that is one host's class name and does not
   * belong hardcoded in a shared package.
   */
  rowClass?: string;

  // — chrome (English defaults; override to translate) —
  /**
   * Display name of the other participant — the contact this conversation is with. It is
   * one name for the whole conversation, so it is a prop rather than a field on every
   * message: the bubble picks it for incoming messages and `youLabel` for outgoing ones.
   *
   * Default "Contact".
   */
  senderName?: string;
  /** default "You" */
  youLabel?: string;
  /** default "Reacted by" */
  reactedByLabel?: string;
  /** default "Reply" */
  replyLabel?: string;
  /** default "Failed to send message" */
  failedMessageLabel?: string;
  /** default "No messages yet" — shown once loading has settled on an empty thread */
  emptyLabel?: string;
  /**
   * default `["👍", "❤️", "😂", "😮", "😢", "🙏"]`
   *
   * The list owns the `ReactionPicker`, not the bubble: the trigger column is a flex
   * sibling of the bubble that swaps side with the row's `flex-row-reverse`, so it cannot
   * move inside {@link MessageBubbleProps} without changing the DOM.
   */
  reactionEmojis?: string[];
}

/**
 * One bubble. Picks its body renderer from the message's content type.
 *
 * Emits: `reply` ({@link WhatsAppMessage}), `jump-to` (`name: string`) — the list, which owns
 * the scroll container, handles the jump.
 */
export interface MessageBubbleProps {
  message: WhatsAppMessage;
  /**
   * Display name of the other participant. Used wherever a name is shown — the reply quote's
   * header and the reaction tooltip — for anything `Incoming`; `youLabel` covers `Outgoing`.
   * Default "Contact".
   */
  senderName?: string;
  /** default "You" */
  youLabel?: string;
  /** default "Reacted by" */
  reactedByLabel?: string;
  /** default "Reply" */
  replyLabel?: string;
  /** default "Failed to send message" */
  failedMessageLabel?: string;
}

/**
 * The tappable button row under a template's body — shared by the sent bubble and the
 * template picker's preview so the two cannot drift apart.
 *
 * Renders nothing at all when there are no buttons, so callers need no `v-if` of their own.
 * The buttons are display only: this is a rendering of what WhatsApp will show on the
 * recipient's phone, not a control surface, so there is no click handling and no emit.
 */
export interface TemplateButtonsProps {
  /** optional because both sources are: a message may not be a template, and a template's
   * child table may not have been fetched — see {@link WhatsAppTemplate.buttons} */
  buttons?: WhatsAppTemplateButton[];
}

// —— the messages controller ——

/**
 * A `[doctype, docname]` pair naming a document messages hang off.
 *
 * `get_messages` takes a list of these and permission-checks every one, so a host decides
 * what a conversation is — one document, or a document plus the record it was converted
 * from — without this package or the app knowing anything about that host.
 */
export type MessageReference = [doctype: string, docname: string];

/** Options for `useMessages()`. Each may be a plain value, a ref, or a getter. */
export interface UseMessagesOptions {
  /**
   * The conversation's scope. **The first pair is where a send attaches**: extra references
   * widen what is read (a Deal's messages plus the Lead's) without changing where new
   * messages land.
   */
  references: MaybeRefOrGetter<MessageReference[]>;
  /** recipient — a `WhatsApp Profile` name or a phone number; required to send */
  to: MaybeRefOrGetter<string | undefined>;
  /** text the draft starts with, e.g. restoring an unsent message */
  initialDraft?: string;
}

/**
 * The controller returned by `useMessages()`: the conversation, everything being composed,
 * and the verbs that change either. It is a `reactive` proxy, so its members read as plain
 * (live) values — spread it onto a component with `v-bind="messages"`. Read members directly
 * (e.g. `messages.draft`); destructuring would drop reactivity.
 *
 * It owns its data: one `createResource` against
 * `whatsapp.whatsapp.api.messages.get_messages`, refetched when the references change, when
 * a verb writes, and when the `whatsapp_message` realtime event names one of the references.
 * The realtime subscription is released when the owning effect scope is disposed.
 */
export interface MessagesController {
  /**
   * The conversation, oldest first. Sorted by `creation` here rather than taken as the
   * server returned it: each reference is read by its own query, so the rows arrive grouped
   * by reference, and a conversation is one chronological run across all of them.
   */
  messages: WhatsAppMessage[];
  /** a fetch is in flight; pair with `messages.length` for a first-load-only spinner */
  loading: boolean;
  /** last failure of a fetch, a send or a reaction; `null` while healthy. Verbs never throw */
  error: unknown;
  /** refetch the conversation; the verbs already do this after a successful write */
  reload: () => Promise<void>;
  /**
   * Send what is staged and clear what the send consumed. Returns the new message's docname,
   * or `null` when there was nothing to send, no recipient, or the call failed (see `error`).
   *
   * A text send clears everything; a **media** send clears only the attachment and the reply,
   * because its body came from `overrides.message` (the caption typed in the preview dialog)
   * and whatever is in the box is a separate, still-unsent message.
   */
  send: (
    overrides?: Pick<SendMessagePayload, "message">
  ) => Promise<string | null>;
  /** react to a message; returns the reaction message's docname, or `null` on failure */
  react: (messageName: string, emoji: string) => Promise<string | null>;

  // — composing —
  /** the text being typed; also the caption of a media send */
  draft: string;
  /** the upload staged by `attach()`, awaiting a send */
  pendingMedia?: MediaFile;
  /** render kind of {@link pendingMedia}; "document" when nothing is staged */
  pendingType: WhatsAppContentType;
  /** the message being replied to, quoted above the input */
  replyTo: WhatsAppMessage | null;
  /** whether `buildPayload()` would return a payload rather than `null` */
  canSend: boolean;
  /** write the draft — the path for a UI bound by `v-bind`, which sees `draft` read-only */
  setDraft: (text: string) => void;
  setReplyTo: (message: WhatsAppMessage) => void;
  clearReply: () => void;
  /** stage an upload; `type` picks its preview and the outgoing content type */
  attach: (file: MediaFile, type?: WhatsAppContentType) => void;
  /** drop the staged upload, e.g. when its preview is dismissed without sending */
  clearAttachment: () => void;
  /**
   * The staged message, or `null` when there is no body and no attachment to send.
   * `overrides.message` supplies a body from outside the draft — a media caption typed in
   * the preview dialog, say — leaving the draft (a separate, unsent message) untouched.
   *
   * `send()` calls this itself; reach for it directly only to inspect what would be sent.
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
  /**
   * DocType the templates are being sent from. It decides which templates are offered:
   * those bound to it (their variables resolve from the open document) plus unbound ones
   * with no variables to resolve.
   */
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
 * The controller returned by `useTemplates()`: the sendable templates for a DocType, and the
 * two writes that go with them. A `reactive` proxy, like {@link MessagesController}.
 *
 * Sending a template does not go through {@link MessagesController}: the body is rendered
 * server-side from the reference document, so there is nothing to compose and no payload.
 */
export interface TemplatesController {
  /** Approved templates sendable from `referenceDoctype`, buttons included */
  templates: WhatsAppTemplate[];
  loading: boolean;
  /** last failure of the fetch or either write; `null` while healthy. Verbs never throw */
  error: unknown;
  reload: () => Promise<void>;
  /** send an approved template; returns the new message's docname, or `null` on failure */
  sendTemplate: (
    templateName: string,
    overrides?: SendTemplateOverrides
  ) => Promise<string | null>;
  /**
   * Create a `WhatsApp Template` and push it to Meta for approval, then refresh the list.
   * `template` is the DocType's own fields; a new template is not sendable until Meta
   * approves it, so it will not appear in `templates` yet.
   */
  createTemplate: (
    template: Record<string, unknown>,
    accountName: string
  ) => Promise<Record<string, unknown> | null>;
}

/**
 * The default input area: textarea, attachment menu, media preview and reply preview. UI
 * only — it holds no composing state and performs no call of its own, reading and writing
 * all of it through the controller spread onto it with `v-bind="messages"`, whose `send()`
 * it invokes. These props are the chrome around that; a host that wants a different input
 * builds one on the same controller and behaves identically.
 *
 * Emits: `send` ({@link SendMessagePayload}) **after** the controller's send lands — a
 * notification (scroll to the bottom, close a drawer), not a request to perform the call.
 * Exposes: `focus()`.
 */
export interface MessageInputProps {
  /** default "Type your message here..." */
  placeholder?: string;
  /** default "Contact" — names an incoming message in the reply preview */
  senderName?: string;
  /** default "You" — names an outgoing message in the reply preview */
  youLabel?: string;
  /** default "Upload Document" */
  uploadDocumentLabel?: string;
  /** default "Upload Image" */
  uploadImageLabel?: string;
  /** default "Upload Video" */
  uploadVideoLabel?: string;
  /** default "Add a caption..." — forwarded to the media preview dialog */
  captionPlaceholder?: string;
  disabled?: boolean;
}

/**
 * One template's body, rendered — header, text, footer and buttons. The template-side
 * counterpart of {@link MessageBubbleProps}: a bubble draws one message, this draws one
 * template.
 *
 * It serves both ends of a template's life, which is the point of it existing. A **sent**
 * template is a {@link WhatsAppMessage}, whose server-rendered `header`/`template`/`footer`
 * feed it; an **unsent** one is a {@link WhatsAppTemplate}, whose `header_text`/`message`/
 * `footer` do. Two field vocabularies, one renderer — so a preview cannot drift from the
 * bubble it becomes.
 *
 * Where it is shown is nobody's business here. A picker, a dialog, a sidebar, a hover card
 * are all host layout; this only draws the content.
 */
export interface TemplateContentProps {
  /** rendered header text — `WhatsAppMessage.header` or `WhatsAppTemplate.header_text` */
  header?: string;
  /**
   * The body. On a sent message this is `template`, already substituted; on an unsent
   * template it is `message`, still carrying its `{{ variables }}`. Either way it renders
   * through the WhatsApp markup formatter, so bold and italic preview the way they send.
   */
  body?: string;
  footer?: string;
  buttons?: WhatsAppTemplateButton[];
  /**
   * Class for the body element only.
   *
   * A fixed-height card wants just the body to scroll, so the footer and buttons — the parts
   * a picker most needs to show — stay pinned instead of being clipped by a long body:
   * `body-class="min-h-0 flex-1 overflow-y-auto"`, with the card itself a flex column.
   */
  bodyClass?: string;
}
