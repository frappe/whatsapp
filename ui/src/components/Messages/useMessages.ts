import { computed, onScopeDispose, reactive, ref, toValue, watch } from "vue";
import { createResource } from "frappe-ui";
import { getSocketInstance } from "../../socket";
import type {
  MediaFile,
  MessageReference,
  MessagesController,
  SendMessagePayload,
  UseMessagesOptions,
  WhatsAppContentType,
  WhatsAppMessage,
} from "./types";

const API = "whatsapp.whatsapp.api.messages";

/**
 * The conversation controller: the messages attached to a set of reference documents, what
 * is being composed for them, and the sends that join the two.
 *
 * It owns its fetching, as `useNotifications` and `useActivityTimeline` do — the endpoints
 * are this app's own and host-agnostic, so nothing here needs a host adapter.
 */
export function useMessages(options: UseMessagesOptions): MessagesController {
  const references = () => toValue(options.references) ?? [];
  const recipient = () => toValue(options.to) ?? "";

  const draft = ref(options.initialDraft ?? "");
  const pendingMedia = ref<MediaFile>();
  const pendingType = ref<WhatsAppContentType>("document");
  const replyTo = ref<WhatsAppMessage | null>(null);
  // Failures a resource cannot hold: the guards this composable applies before calling one.
  const guardError = ref<unknown>(null);

  const list = createResource({
    url: `${API}.get_messages`,
    // `references` is annotated `str` on the endpoint and the app validates whitelisted
    // arguments against those annotations, so the pairs must travel as JSON text — a raw
    // array is rejected before the method runs.
    makeParams: () => ({ references: JSON.stringify(references()) }),
  });

  const sendResource = createResource({ url: `${API}.send_message` });
  const reactResource = createResource({ url: `${API}.react_to_message` });

  // Sorted here, not taken as given: `get_messages` reads each reference with its own query
  // and `WhatsApp Message` sorts `creation desc` by default, so the rows arrive newest-first
  // and grouped by reference. A conversation is one chronological run across every reference.
  // `creation` is an ISO-ish stamp, so it compares correctly as a string.
  const messages = computed<WhatsAppMessage[]>(() =>
    [...((list.data as WhatsAppMessage[]) ?? [])].sort((a, b) =>
      (a.creation ?? "") < (b.creation ?? "") ? -1 : 1
    )
  );
  const loading = computed<boolean>(() => Boolean(list.loading));
  // Surfaced rather than toasted: this package has no notification surface of its own, and a
  // host's is its own choice. A resource clears its error when its next call starts.
  const error = computed<unknown>(
    () =>
      guardError.value ??
      list.error ??
      sendResource.error ??
      reactResource.error
  );

  async function reload() {
    try {
      await list.reload();
    } catch {
      // reported through `error`
    }
  }

  function setDraft(text: string) {
    draft.value = text;
  }

  function setReplyTo(message: WhatsAppMessage) {
    replyTo.value = message;
  }

  function clearReply() {
    replyTo.value = null;
  }

  /** Stage an upload for the next send; `type` picks the preview and the outgoing kind. */
  function attach(file: MediaFile, type: WhatsAppContentType = "document") {
    pendingMedia.value = file;
    pendingType.value = type;
  }

  /** Drop the staged upload — an abandoned attachment must not ride along on the next send. */
  function clearAttachment() {
    pendingMedia.value = undefined;
    pendingType.value = "document";
  }

  // Same guard buildPayload() applies, exposed so an input can disable its send affordance
  // instead of letting a click no-op.
  const canSend = computed(() =>
    Boolean(draft.value.trim() || pendingMedia.value)
  );

  /**
   * Assemble what is currently staged, or `null` when there is nothing to send — no body
   * and no attachment. A bare attachment is valid; an empty message is not.
   *
   * `overrides.message` supplies a body from somewhere other than the draft. A media
   * caption is typed in the preview dialog, not in the input, and the draft it leaves
   * behind is a separate unsent message — passing the caption here keeps the two apart
   * instead of one overwriting the other. The guard applies to whichever body wins.
   */
  function buildPayload(
    overrides?: Pick<SendMessagePayload, "message">
  ): SendMessagePayload | null {
    const message = overrides?.message ?? draft.value;
    const attachment = pendingMedia.value;
    if (!message.trim() && !attachment) return null;
    return {
      message,
      attach: attachment?.file_url,
      contentType: attachment ? pendingType.value : "text",
      replyTo: replyTo.value?.name,
    };
  }

  /** Clear everything a text send consumed — the draft, the attachment and the reply. */
  function reset() {
    draft.value = "";
    clearAttachment();
    replyTo.value = null;
  }

  async function send(
    overrides?: Pick<SendMessagePayload, "message">
  ): Promise<string | null> {
    // Read synchronously, before any await: dismissing the media preview clears the
    // attachment, and that happens while this call is in flight.
    const payload = buildPayload(overrides);
    if (!payload) return null;

    guardError.value = null;
    const to = recipient();
    if (!to) {
      guardError.value = new Error(
        "Cannot send: useMessages() was given no recipient (`to`)."
      );
      return null;
    }

    const [referenceDoctype, referenceDocname] = references()[0] ?? [];

    let name: string | null = null;
    try {
      name = (await sendResource.submit({
        to,
        message: payload.message,
        attach: payload.attach,
        content_type: payload.contentType,
        reply_to: payload.replyTo,
        reference_doctype: referenceDoctype,
        reference_docname: referenceDocname,
      })) as string;
    } catch {
      // reported through `error`; the draft survives so the send can be retried
      return null;
    }

    if (payload.attach) {
      clearAttachment();
      clearReply();
    } else {
      reset();
    }

    await reload();
    return name;
  }

  async function react(
    messageName: string,
    emoji: string
  ): Promise<string | null> {
    guardError.value = null;
    try {
      const name = (await reactResource.submit({
        message: messageName,
        emoji,
      })) as string;
      await reload();
      return name;
    } catch {
      return null;
    }
  }

  // A stable key, so a getter that rebuilds an equal array does not refetch on every tick.
  const referencesKey = computed(() => JSON.stringify(references()));
  watch(referencesKey, () => reload(), { immediate: true });

  const socket = getSocketInstance();
  if (socket) {
    // Published by the app's `WhatsApp Message.on_update`, so an inbound message, a status
    // change and another agent's send all land here.
    const onMessage = (payload: unknown) => {
      const event = (payload ?? {}) as Partial<
        Record<"reference_doctype" | "reference_docname", string>
      >;
      const concerns = references().some(
        ([doctype, docname]: MessageReference) =>
          doctype === event.reference_doctype &&
          docname === event.reference_docname
      );
      if (concerns) reload();
    };

    socket.on("whatsapp_message", onMessage);
    // Scope disposal, not unmount: the controller belongs to whatever scope created it, and
    // a host may keep one alive across a component's lifetime.
    onScopeDispose(() => socket.off("whatsapp_message", onMessage));
  }

  // Returned as a `reactive` object so a component can spread it with `v-bind="messages"`:
  // `v-bind` does not unwrap refs nested in a plain object, but `reactive` unwraps them, so
  // each member binds as a live value. Read members off the returned object
  // (e.g. `messages.draft`) rather than destructuring, which would drop reactivity.
  return reactive({
    messages,
    loading,
    error,
    reload,
    send,
    react,
    draft,
    pendingMedia,
    pendingType,
    replyTo,
    canSend,
    setDraft,
    setReplyTo,
    clearReply,
    attach,
    clearAttachment,
    buildPayload,
    reset,
  }) as MessagesController;
}
