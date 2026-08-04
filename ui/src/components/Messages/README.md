# MessagePanel

A WhatsApp conversation UI: the messages attached to one or more reference documents, drawn
as a flat list in send order, plus the input that sends into it.

The components are **UI only**. Data is a plugin the host owns: call `useMessages()` to get a
controller, then spread it onto the panel and the input with `v-bind`. The controllers own the
fetching and the writing — they call this app's own whitelisted endpoints, so there is no
host adapter to write and no host endpoint to build. This is the same shape as
`@framework/ui`'s `useNotifications()` / `NotificationPanel`.

`MessageInput` is the input that ships with the package. It has no privileged access to the
controller, so you can replace it with your own without losing any behaviour.

## Usage

Batteries included — the panel, the controller, and the default input:

```vue
<script setup lang="ts">
import { MessageInput, MessagePanel, useMessages, useTemplates } from "@whatsapp/ui";
import type { ReactPayload } from "@whatsapp/ui";

const props = defineProps<{
  doctype: string;
  docname: string;
  contactName: string;
  phone: string;
}>();

const messages = useMessages({
  references: () => [[props.doctype, props.docname]],
  to: () => props.phone,
});

const templates = useTemplates({
  referenceDoctype: () => props.doctype,
  referenceDocname: () => props.docname,
  to: () => props.phone,
});

function react({ messageName, emoji }: ReactPayload) {
  messages.react(messageName, emoji);
}

async function sendTemplate(templateName: string) {
  // The two controllers are independent, so a template send does not refresh the
  // conversation by itself. (With a socket wired up the realtime event does it for you.)
  if (await templates.sendTemplate(templateName)) messages.reload();
}
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- MessagePanel sets inheritAttrs: false — wrap it to size or space it -->
    <div class="min-h-0 flex-1">
      <MessagePanel
        v-bind="messages"
        :templates="templates.templates"
        :sender-name="contactName"
        @reply="messages.setReplyTo"
        @react="react"
        @send-template="sendTemplate"
      />
    </div>
    <MessageInput v-bind="messages" :sender-name="contactName" />
  </div>
</template>
```

`v-bind="messages"` spreads the controller's **data** members as props (the controller is a
`reactive` object, so each binds as a live value — don't destructure it), along with its verbs,
which is how `MessageInput` writes back. The panel's own actions are **events**: wire `@reply`
to `setReplyTo` so a message picked in the list becomes the reply the input quotes, and
`@react` to `react()`.

`MessageInput` calls `messages.send()` itself and emits `send` only **after** the send lands —
that is a notification (scroll to the bottom, close a drawer), not a request to perform the
call. The controller clears what the send consumed: a text send is a full `reset()`, a media
send clears only the attachment and the reply, because its body was the caption and whatever
is still typed in the box is a separate unsent message.

Omit `:templates` and the template flow disappears entirely — the panel does not render the
selector dialog at all.

### Roll your own input

The same controller, no `MessageInput`:

```vue
<script setup lang="ts">
import { useMessages } from "@whatsapp/ui";

const props = defineProps<{
  doctype: string;
  docname: string;
  contactName: string;
  phone: string;
}>();

const messages = useMessages({
  references: () => [[props.doctype, props.docname]],
  to: () => props.phone,
});

async function submit() {
  // send() applies the empty-send guard itself and returns null when there was nothing
  // to send, no recipient, or the call failed — see `messages.error`.
  await messages.send();
}
</script>

<template>
  <div v-if="messages.replyTo">
    Replying to {{ messages.replyTo.direction === "Incoming" ? contactName : "You" }}
    <button @click="messages.clearReply()">×</button>
  </div>
  <textarea v-model="messages.draft" @keydown.enter.exact.prevent="submit" />
  <button :disabled="!messages.canSend" @click="submit">Send</button>
</template>
```

A controller you hold directly can be written straight (`messages.draft = "hi"`, because it is
`reactive`); one arriving through `v-bind` is read-only, which is what `setDraft` is for.

If you build your own media flow, stage the upload with `attach(file, type)` and send the
caption as an **override** rather than writing it into the draft — the draft is whatever the
user has typed in the box, and a caption typed in a preview dialog is a different message:

```ts
async function sendMedia(file: MediaFile, caption: string) {
  messages.attach(file, "image");
  await messages.send({ message: caption });
}
```

The empty-send guard applies to whichever body wins, so an attachment with no caption still
sends and a bare empty text send still returns `null`. `buildPayload(overrides?)` exposes the
same assembly if you want to inspect what would go out; it never sends.

### `useMessages`

```ts
const messages = useMessages({
  references, // [doctype, docname] pairs — the conversation's scope
  to, // recipient: a WhatsApp Profile name or a phone number
  initialDraft, // optional: text the draft starts with
});

// controller (a reactive object):
// messages, loading, error, reload, send, react,
// draft, pendingMedia, pendingType, replyTo, canSend,
// setDraft, setReplyTo, clearReply, attach, clearAttachment, buildPayload, reset
```

`references` and `to` each accept a plain value, a ref, or a getter. Pass a getter (or a ref)
whenever they can change — the conversation refetches when the reference list changes.

**`references[0]` is where a send attaches.** Extra references only widen the read. So a CRM
Deal that should also show the messages of the Lead it was converted from passes both, and new
messages still land on the Deal:

```ts
import { computed } from "vue";
import type { MessageReference } from "@whatsapp/ui";

const references = computed<MessageReference[]>(() => {
  const list: MessageReference[] = [["CRM Deal", props.deal]];
  if (props.lead) list.push(["CRM Lead", props.lead]);
  return list;
});

const messages = useMessages({ references, to: () => props.phone });
```

`messages` is sorted oldest-first across every reference: each one is read by its own query,
so the rows arrive grouped, and a conversation is one chronological run through all of them.

`error` holds the last failure of the fetch, a send or a reaction, and is `null` while
healthy. The verbs never throw — they return `null` — because this package has no notification
surface of its own and a host's is its own choice. Render `error` where your app renders
errors.

### `useTemplates`

```ts
const templates = useTemplates({
  referenceDoctype, // decides which templates are offered
  referenceDocname, // optional: the document a sent template attaches to
  to, // optional: default recipient for sendTemplate()
});

// controller (a reactive object):
// templates, loading, error, reload, sendTemplate, createTemplate
```

Kept apart from `useMessages()` because a template send composes nothing — the body is
rendered server-side from the reference document — and because the offering is a property of
the DocType, not of the conversation. `sendTemplate(name, { to?, referenceDocname? })` returns
the new message's docname or `null`; `createTemplate(fields, accountName)` creates a
`WhatsApp Template` and pushes it to Meta, then refreshes the list (a new template is not
sendable until Meta approves it, so it will not appear yet).

### Sender name is a prop, not a field

Nothing on the wire says who sent a message beyond its `direction`. Who that *is* is one
string for the whole conversation, so it is a prop:

- `Incoming` → `senderName` (default `"Contact"`) — the contact you are talking to.
- `Outgoing` → `youLabel` (default `"You"`).

That one rule covers every place a name appears: the reply quote's header, the reaction
tooltip (`reactedByLabel`), and the input's reply preview. `MessagePanel`, `MessageList`,
`MessageBubble` and `MessageInput` all take both props. There is no `from_name` field and no
reactor name on a reaction — see
[ADR-0003](../../../docs/adr/0003-the-app-owns-the-message-api.md).

### Realtime

`useMessages()` resolves the host's socket.io connection with `getSocketInstance()` and
subscribes to the app's `whatsapp_message` event, reloading when the event names one of its
references. That covers an inbound message, a status change, and another agent's send.

Expose the socket at your app root with `provide("socket", socket)` (`"$socket"` and an
`app.config.globalProperties.$socket` global are also read). **With no socket the subscription
is skipped entirely** — everything else works, the conversation just refreshes only on the
controller's own writes and on `reload()`. The subscription is released on effect-scope
dispose, so a controller held longer than a component is still cleaned up correctly.

`useMessages()` injects, so it must be called during `setup()`.

### Exposed methods

`MessagePanel` owns its template dialog, so a host toolbar can drive it through a template ref
rather than through a boolean:

```vue
<MessagePanel ref="panel" ... />
<Button label="Templates" @click="panel.openTemplateSelector()" />
```

Bind `v-model:templatesOpen` instead if you would rather hold the dialog's state yourself.
`MessageInput` exposes `focus()`, and focuses itself whenever `replyTo` becomes set.

### `inheritAttrs: false`

`MessagePanel` and `MessageInput` both set it, following `NotificationPanel`. The panel is
bound with `v-bind="controller"`, which lands the controller's verbs on it as fall-through
attrs; inheriting those onto the root element would stamp function-valued attributes into the
DOM. The input's template has multiple roots, which Vue cannot auto-inherit onto at all.

The practical consequence differs between the two:

- **`MessagePanel` does not re-bind `$attrs`**, so a `class` you pass it is dropped. Wrap it in
  an element you style instead.
- **`MessageInput` binds `$attrs` onto its input row**, so a `class` does land — on the row,
  not on the reply preview above it.

## What a host still needs to know about the data

The server returns the view model directly: `get_messages` folds reactions onto their targets,
renders template bodies, resolves reply quotes, joins `File` for attachment name and size, and
reduces Meta's raw failure payload to a human sentence. There is nothing to derive on the
client and nothing to rename.

Two things do not come from a column, and a host writing its own rendering needs them:

- **`status` is Title Case.** `Pending` / `Sent` / `Delivered` / `Read` / `Failed`, exactly as
  stored. Do not lowercase it at any boundary — the tick renderer compares against these
  literals, and `Pending` (the DocType default) deliberately renders no tick.
- **Render kind comes from `mime_type`.** `contentTypeFromMime()` maps an `image/`, `audio/` or
  `video/` prefix to that kind, any other MIME type to `document`, and no MIME type at all to
  `text`. There is no stored column behind it and nothing to override.

### Security

The endpoints guard on the **reference document**: every `[doctype, docname]` pair handed to
`get_messages` is checked for existence and `has_permission("read")`, and the write endpoints
check the message and its reference the same way.

The WhatsApp app has **no role model of its own yet** (its open gap
[#10](https://github.com/ps173/frappe-whatsapp/issues/10) — everything else requires System
Manager). So this check is *orthogonal* to a host's role policy, not a superset of it: a host
that gates WhatsApp access by role must keep that gate in front of these endpoints rather than
assume the app's reference check subsumes it.

## Deliberately absent

- **No emoji picker.** Reactions are a fixed six-emoji bar (`REACTION_EMOJIS`, overridable via
  `reactionEmojis`). Typing emoji is the OS keyboard's job.
- **No i18n.** Every user-facing string is an English-defaulted prop — `placeholder`,
  `youLabel`, `replyLabel`, `emptyLabel`, and so on. Pass your own translations in.
- **No toasts or error dialogs.** Failures are surfaced on the controller's `error`; where an
  app shows errors is the app's decision.
- **No account or settings management.** Choosing the WhatsApp account and enabling the
  channel stay in the host (or the desk UI). Editing templates is desk-side too — the
  selector's "Create New" opens this app's own form.

## Backend

Requires the `whatsapp` app on the site. The controllers call these whitelisted methods.

From `whatsapp.whatsapp.api.messages`:

```
get_messages(references)
send_message(to, message, attach, content_type, reply_to, reference_doctype, reference_docname)
react_to_message(message, emoji)
send_template(template, to, reference_doctype, reference_docname)
```

From `whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template`:

```
get_sendable_templates(reference_doctype)
create_template_and_push(doc_data, account_name)
```

`references` travels as a **JSON string** — the app validates whitelisted arguments against
their type annotations, and that parameter is annotated `str`, so a raw array is rejected
before the method runs. `useMessages()` stringifies it for you.

Realtime updates listen on the `whatsapp_message` event, published by
`WhatsApp Message.on_update` with the reference doctype and docname.

## Types

`WhatsAppMessage`, `WhatsAppTemplate`, `WhatsAppReaction`, `WhatsAppTemplateButton`,
`WhatsAppDirection`, `WhatsAppStatus`, `WhatsAppContentType`, `MediaFile`, `MessageReference`,
`SendMessagePayload`, `ReactPayload`, `UseMessagesOptions`, `MessagesController`,
`UseTemplatesOptions`, `TemplatesController`, `SendTemplateOverrides`, `MessagePanelProps`,
`MessageListProps`, `MessageBubbleProps`, `MessageInputProps`, `MediaPreviewDialogProps`,
`TemplateSelectorDialogProps`, `TemplateButtonsProps`, `ReactionPickerProps`.
