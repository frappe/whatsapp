import {
  computed,
  onScopeDispose,
  reactive,
  ref,
  toValue,
  watch,
} from "vue";
import { createResource, dayjs, dayjsLocal, getConfig } from "frappe-ui";
import { getSocketInstance, subscribeToDoc } from "@framework/ui/socket";
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

// Only the prefix matters: `contentTypeFromMime` picks the renderer from it.
const PLACEHOLDER_MIME: Record<WhatsAppContentType, string | undefined> = {
  text: undefined,
  image: "image/*",
  video: "video/*",
  audio: "audio/*",
  document: "application/octet-stream",
};

/** Now as `creation` is stored: naive, in the site's timezone, which `dayjsLocal` assumes. */
function systemNow(): string {
  const timezone = getConfig("systemTimezone");
  return (timezone ? dayjs().tz(timezone) : dayjs()).format("YYYY-MM-DD HH:mm:ss");
}

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
  // Sends shown before the server has answered. They always go last, so the browser's
  // clock never has to agree with the server's.
  const placeholders = ref<WhatsAppMessage[]>([]);
  const messages = computed<WhatsAppMessage[]>(() => [
    ...[...((list.data as WhatsAppMessage[]) ?? [])].sort((a, b) =>
      (a.creation ?? "") < (b.creation ?? "") ? -1 : 1
    ),
    ...placeholders.value,
  ]);
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

  const inFlight = ref(0);
  const sending = computed(() => inFlight.value > 0);

  // The composer is cleared the moment a send starts, so a second enter has nothing to post
  // twice and the next message can be sent before the last one lands.
  const canSend = computed(() => Boolean(draft.value.trim() || pendingMedia.value));

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

  // Sends go out one at a time, so they reach WhatsApp in the order they were typed.
  let sendQueue: Promise<unknown> = Promise.resolve();
  let placeholderCount = 0;

  async function send(
    overrides?: Pick<SendMessagePayload, "message">
  ): Promise<string | null> {
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
    const repliedTo = replyTo.value;
    const placeholder = placeholderFor(payload, repliedTo);
    placeholders.value.push(placeholder);
    consume(payload);

    const request = sendQueue.then(() =>
      sendResource.submit({
        to,
        message: payload.message,
        attach: payload.attach,
        content_type: payload.contentType,
        reply_to: payload.replyTo,
        reference_doctype: referenceDoctype,
        reference_docname: referenceDocname,
      })
    );
    sendQueue = request.catch(() => {});

    inFlight.value++;
    try {
      const name = (await request) as string;
      // A send WhatsApp refuses still returns a name: the reload brings its Failed row.
      await reload();
      return name;
    } catch {
      // reported through `error`
      restore(payload, repliedTo);
      return null;
    } finally {
      placeholders.value = placeholders.value.filter((m) => m.name !== placeholder.name);
      inFlight.value--;
    }
  }

  /** A text send takes the draft; a media send's body is the caption, so the draft stays. */
  function consume(payload: SendMessagePayload) {
    if (payload.attach) {
      clearAttachment();
      clearReply();
    } else {
      reset();
    }
  }

  /** Put a failed text send back in the box, unless the next message is already in it. */
  function restore(payload: SendMessagePayload, repliedTo: WhatsAppMessage | null) {
    if (payload.attach || draft.value || replyTo.value) return;
    draft.value = payload.message;
    replyTo.value = repliedTo;
  }

  function placeholderFor(
    payload: SendMessagePayload,
    repliedTo: WhatsAppMessage | null
  ): WhatsAppMessage {
    const attachment = pendingMedia.value;
    return {
      name: `placeholder-${++placeholderCount}`,
      direction: "Outgoing",
      creation: systemNow(),
      message: payload.message,
      status: "Sent",
      media_url: payload.attach,
      mime_type: attachment ? PLACEHOLDER_MIME[payload.contentType] : undefined,
      file_name: attachment?.file_name,
      file_size: attachment?.file_size,
      reply_to: repliedTo?.name,
      reply_message: repliedTo?.is_template ? repliedTo.template : repliedTo?.message,
      reply_to_direction: repliedTo?.direction,
    };
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
