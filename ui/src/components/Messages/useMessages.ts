import {
  computed,
  getCurrentInstance,
  inject,
  onScopeDispose,
  reactive,
  ref,
  toValue,
  watch,
} from "vue";
import { createResource } from "frappe-ui";
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

/** The socket methods used here. Structural, so this package never imports socket.io. */
interface RealtimeSocket {
  emit(event: string, ...args: unknown[]): void;
  on(event: string, handler: (...args: unknown[]) => void): void;
  off(event: string, handler: (...args: unknown[]) => void): void;
}

/**
 * The host's existing connection, never a new one — frappe-ui's `initSocket()` would open a
 * second. Its plugin sets the `$socket` global this reads; a host may `provide()` one instead.
 */
function resolveSocket(): RealtimeSocket | undefined {
  const instance = getCurrentInstance();
  if (!instance) {
    throw new Error("useMessages() must be called during setup().");
  }

  const globals = instance.appContext.config.globalProperties;
  const socket =
    inject<RealtimeSocket | undefined>("socket", undefined) ??
    inject<RealtimeSocket | undefined>("$socket", undefined) ??
    (globals.socket as RealtimeSocket | undefined) ??
    (globals.$socket as RealtimeSocket | undefined);

  if (!socket && import.meta.env?.DEV) {
    console.warn(
      "useMessages: no socket found, so live updates are off. Expose one via " +
        "provide('socket'|'$socket', …) or a $socket global."
    );
  }

  return socket;
}

/**
 * The conversation controller: the messages attached to a set of reference documents, what
 * is being composed for them, and the sends that join the two.
 */
export function useMessages(options: UseMessagesOptions): MessagesController {
  const references = () => toValue(options.references) ?? [];
  const recipient = () => toValue(options.to) ?? "";

  const draft = ref(options.initialDraft ?? "");
  const pendingMedia = ref<MediaFile>();
  const pendingType = ref<WhatsAppContentType>("document");
  const replyTo = ref<WhatsAppMessage | null>(null);
  // Failures a resource cannot hold: the guards applied before calling one.
  const guardError = ref<unknown>(null);

  const list = createResource({
    url: `${API}.get_messages`,
    // The endpoint annotates `references` as `str` and the app validates whitelisted
    // arguments against those annotations, so a raw array is rejected before it runs.
    makeParams: () => ({ references: JSON.stringify(references()) }),
  });

  const sendResource = createResource({ url: `${API}.send_message` });
  const reactResource = createResource({ url: `${API}.react_to_message` });

  // `get_messages` reads each reference with its own query, so rows arrive grouped by
  // reference. `creation` is an ISO-ish stamp, so it compares correctly as a string.
  const messages = computed<WhatsAppMessage[]>(() =>
    [...((list.data as WhatsAppMessage[]) ?? [])].sort((a, b) =>
      (a.creation ?? "") < (b.creation ?? "") ? -1 : 1
    )
  );
  const loading = computed<boolean>(() => Boolean(list.loading));
  // A resource clears its error when its next call starts.
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

  function attach(file: MediaFile, type: WhatsAppContentType = "document") {
    pendingMedia.value = file;
    pendingType.value = type;
  }

  /** An abandoned attachment must not ride along on the next send. */
  function clearAttachment() {
    pendingMedia.value = undefined;
    pendingType.value = "document";
  }

  // Guards the double-send: `send()` awaits, and without this a second ctrl+enter during
  // the round trip posts the same draft twice.
  const sending = ref(false);

  const canSend = computed(
    () => !sending.value && Boolean(draft.value.trim() || pendingMedia.value)
  );

  /**
   * `overrides.message` supplies a body from outside the draft — a caption typed in the
   * preview dialog — so the draft survives as the separate unsent message it is.
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

  function reset() {
    draft.value = "";
    clearAttachment();
    replyTo.value = null;
  }

  async function send(
    overrides?: Pick<SendMessagePayload, "message">
  ): Promise<string | null> {
    // Read before any await: dismissing the media preview clears the attachment, and that
    // happens while this call is in flight.
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
    sending.value = true;
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
    } finally {
      sending.value = false;
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

  const socket = resolveSocket();
  if (socket) {
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

    // The app publishes on each reference document's room, and a client is in no room until
    // it asks: `doc_subscribe` is what the socket server permission-checks and joins.
    let subscribed: MessageReference[] = [];
    const unsubscribeAll = () => {
      for (const [doctype, docname] of subscribed) {
        socket.emit("doc_unsubscribe", doctype, docname);
      }
    };
    const resubscribe = () => {
      unsubscribeAll();
      subscribed = [...references()];
      for (const [doctype, docname] of subscribed) {
        socket.emit("doc_subscribe", doctype, docname);
      }
    };
    watch(referencesKey, resubscribe, { immediate: true });

    socket.on("whatsapp_message", onMessage);
    // Scope disposal, not unmount: a host may keep a controller alive across a component.
    onScopeDispose(() => {
      socket.off("whatsapp_message", onMessage);
      unsubscribeAll();
    });
  }

  // `reactive`, not a plain object: `v-bind` does not unwrap nested refs but `reactive`
  // does, so each member binds as a live value.
  return reactive({
    messages,
    loading,
    sending,
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
