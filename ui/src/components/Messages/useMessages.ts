import {
  computed,
  onScopeDispose,
  reactive,
  ref,
  toValue,
  watch,
} from "vue";
import { createResource, dayjsLocal } from "frappe-ui";
import { getSocketInstance, subscribeToDoc } from "@framework/ui";
import type {
  CustomerServiceWindow,
  MediaFile,
  MessageReference,
  MessagesController,
  SendMessagePayload,
  UseMessagesOptions,
  WhatsAppContentType,
  WhatsAppMessage,
} from "./types";

const API = "whatsapp.whatsapp.api.messages";
const CUSTOMER_SERVICE_WINDOW_HOURS = 24;

/**
 * The conversation controller: the messages attached to a set of reference documents, what
 * is being composed for them, and the sends that join the two.
 */
export function useMessages(options: UseMessagesOptions): MessagesController {
  const references = () => toValue(options.references) ?? [];
  const recipient = () => toValue(options.to) ?? "";
  const enabled = () => toValue(options.enabled) ?? true;

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

  // `now` is only bumped at the expiry instant, so a tab left open across the boundary
  // locks its composer the moment the window closes rather than on its next reload.
  const now = ref(Date.now());
  const serviceWindow = computed<CustomerServiceWindow | null>(() => {
    if (list.data == null) return null;
    const last = messages.value[messages.value.length - 1];
    if (!last?.creation) return { status: "unopened", expiresAt: null };
    const expiresAt = dayjsLocal(last.creation).add(CUSTOMER_SERVICE_WINDOW_HOURS, "hour");
    return {
      status: expiresAt.valueOf() > now.value ? "open" : "closed",
      expiresAt: expiresAt.toDate(),
    };
  });

  let expiryTimer: ReturnType<typeof setTimeout> | undefined;
  watch(
    () => serviceWindow.value?.expiresAt?.valueOf(),
    (expiresAt) => {
      clearTimeout(expiryTimer);
      const wait = (expiresAt ?? 0) - Date.now();
      if (wait > 0) expiryTimer = setTimeout(() => (now.value = Date.now()), wait);
    },
    { immediate: true }
  );
  onScopeDispose(() => clearTimeout(expiryTimer));
  // A resource clears its error when its next call starts.
  const error = computed<unknown>(
    () =>
      guardError.value ??
      list.error ??
      sendResource.error ??
      reactResource.error
  );

  async function reload() {
    if (!enabled()) return;
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

  // Guards the double-send: `send()` awaits, and without this a second enter during the
  // round trip posts the same draft twice.
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

    // The composer stays editable while the send is in flight, so only what was sent is
    // cleared: a draft, attachment or reply chosen meanwhile is the next message.
    if (pendingMedia.value?.file_url === payload.attach) clearAttachment();
    if (replyTo.value?.name === payload.replyTo) clearReply();
    if (!payload.attach && draft.value === payload.message) draft.value = "";

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
  watch([referencesKey, enabled], () => reload(), { immediate: true });

  const socket = getSocketInstance();
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

    // Rooms are shared with every other consumer of the same document (a host's activity
    // timeline, say), so they are held through @framework/ui's counted table: a bare
    // `doc_unsubscribe` from either side would drop the other out of the room. The new rooms
    // are held before the old are released, so an unchanged room is never left and rejoined.
    let leaveRooms: Array<() => void> = [];
    const leaveAll = () => {
      for (const leave of leaveRooms) leave();
      leaveRooms = [];
    };
    const holdRooms = () => {
      const held = enabled()
        ? references().map(([doctype, docname]) =>
            subscribeToDoc(socket, doctype, docname)
          )
        : [];
      leaveAll();
      leaveRooms = held;
    };
    watch([referencesKey, enabled], holdRooms, { immediate: true });

    // The rooms are rejoined on reconnect, but nothing was buffered while the socket was
    // down, so whatever arrived in the gap is fetched once it is back.
    let dropped = false;
    const onDisconnect = () => (dropped = true);
    const onConnect = () => {
      if (!dropped) return;
      dropped = false;
      reload();
    };

    socket.on("whatsapp_message", onMessage);
    socket.on("disconnect", onDisconnect);
    socket.on("connect", onConnect);
    // Scope disposal, not unmount: a host may keep a controller alive across a component.
    onScopeDispose(() => {
      socket.off("whatsapp_message", onMessage);
      socket.off("disconnect", onDisconnect);
      socket.off("connect", onConnect);
      leaveAll();
    });
  }

  // `reactive`, not a plain object: `v-bind` does not unwrap nested refs but `reactive`
  // does, so each member binds as a live value.
  return reactive({
    messages,
    loading,
    sending,
    error,
    serviceWindow,
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
