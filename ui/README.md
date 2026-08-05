# @whatsapp/ui

Shared WhatsApp message components for Frappe apps: the messages attached to one or more
reference documents, drawn as a flat list in send order, plus the input that sends into it.

The package ships **raw `.vue`/`.ts` source** — there is no build step and no published
bundle. The host app's bundler compiles it in place, so the host owns the toolchain,
the Tailwind scan, and the typecheck.

It ships components *and* the composables that feed them. `useMessages()` and
`useTemplates()` call the WhatsApp app's own whitelisted endpoints, so a host mounts the UI
and binds a controller — it does not write an API or a mapping layer. See [Usage](#usage).

## Installation into a host app

1. Link the package from the host's `frontend/package.json`:

   ```json
   "dependencies": {
     "@whatsapp/ui": "link:../../whatsapp/ui"
   }
   ```

2. Alias it in the host's `vite.config.js` and dedupe the shared singletons:

   ```js
   resolve: {
     alias: {
       // point at the package's src dir, not src/index.ts, so subpath imports
       // like `@whatsapp/ui/components/Messages` resolve to a real file
       '@whatsapp/ui': path.resolve(__dirname, '../../whatsapp/ui/src'),
     },
     dedupe: ['vue', 'frappe-ui', 'reka-ui', 'dompurify'],
   }
   ```

   Instead of hand-writing the `dedupe` array you can add the plugin, which sets the
   same list via `config()`:

   ```js
   import whatsappUI from '@whatsapp/ui/vite'
   // ...
   plugins: [whatsappUI()]
   ```

See `apps/crm-eventfix/frontend/vite.config.js` for the same setup applied to
`@framework/ui`.

## Host build requirements for icons

Icons come from frappe-ui's lucide integration, in both of its forms — so a host has to
enable **both**, or icons go missing.

1. **The vite plugin**, for the `~icons/lucide/*` imports (`TemplateButtons` picks its icon
   from `button_type` at runtime, which a class name cannot express):

   ```js
   frappeui({ lucideIcons: true })
   ```

2. **A Tailwind `content` glob covering this package**, for the `lucide-*` utility classes
   used everywhere else. Tailwind only generates CSS for classes it finds as complete strings
   in the files it scans, and it does not scan a linked package by default:

   ```js
   // tailwind.config.js
   content: [
     './src/**/*.{vue,js,ts,jsx,tsx}',
     '../../whatsapp/ui/src/**/*.{vue,js,ts,jsx,tsx}',   // ← this package
   ]
   ```

   **Miss this one and nothing errors** — every class-form icon simply renders as empty
   space. `crm-eventfix` already carries the equivalent line for `@framework/ui`.

## Do not install `frappe-ui` or `vue` here

`frappe-ui` and `vue` are **peer dependencies** and must never end up in this package's
`node_modules`. A second copy of either means two module instances at runtime: Vue's
`provide`/`inject` keys stop matching across the boundary (reka-ui, which frappe-ui builds
on, relies on injected context throughout), and two Vue runtimes break reactivity between
host and library components. The host supplies the single copy; the `dedupe` list above is
what keeps it single.

`dompurify` is the only real dependency.

## Usage

The components are **UI only**. Call `useMessages()` to get a controller, then bind it onto
the list and spread it onto the input. The controllers own the fetching and the writing, so
there is no host adapter to write and no host endpoint to build — the same shape as
`@framework/ui`'s `useNotifications()`.

There is no all-in-one panel component. The host composes the list, the input and the
template picker, because it is the host that decides where a conversation sits, what scrolls,
and what the toolbar above it does.

```vue
<script setup lang="ts">
import { MessageInput, MessageList, useMessages } from "@whatsapp/ui";
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

function react({ messageName, emoji }: ReactPayload) {
  messages.react(messageName, emoji);
}
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- the host owns the scroll container; MessageList is layout-neutral -->
    <div class="min-h-0 flex-1 overflow-y-auto px-3 py-4 sm:px-10">
      <MessageList
        :messages="messages.messages"
        :loading="messages.loading"
        :sender-name="contactName"
        @reply="messages.setReplyTo"
        @react="react"
      />
    </div>
    <MessageInput v-bind="messages" :sender-name="contactName" />
  </div>
</template>
```

`MessageList` takes explicit props, so bind the two it reads (`messages`, `loading`) rather
than spreading the whole controller — the controller's verbs would otherwise land on it as
fall-through attrs and be stamped into the DOM. Its actions are **events**: wire `@reply` to
`setReplyTo` so a message picked in the list becomes the reply the input quotes, and `@react`
to `react()`.

`MessageInput` is the one component that *does* take the whole controller.
`v-bind="messages"` spreads its data members as props (the controller is a `reactive` object,
so each binds as a live value — don't destructure it) along with its verbs, which is how the
input writes back. It has no privileged access, so you can replace it with your own without
losing any behaviour.

It calls `messages.send()` itself and emits `send` only **after** the send lands — that is a
notification (scroll to the bottom, close a drawer), not a request to perform the call. The
controller clears what the send consumed: a text send is a full `reset()`, a media send
clears only the attachment and the reply, because its body was the caption and whatever is
still typed in the box is a separate unsent message.

### Sending a template

There is no template picker in this package. `useTemplates()` fetches the sendable templates
and sends one; `TemplateContent` draws one; **where they are shown is the host's decision** —
a dialog, a sidebar, a dropdown, a slash-command menu. Search, the grid and the "create a
template" affordance are all host chrome.

```vue
<script setup lang="ts">
import { TemplateContent, useTemplates } from "@whatsapp/ui";

const templates = useTemplates({
  referenceDoctype: () => props.doctype,
  referenceDocname: () => props.docname,
  to: () => props.phone,
});

async function send(templateName: string) {
  // The two controllers are independent, so a template send does not refresh the
  // conversation by itself. (With a socket wired up the realtime event does it for you.)
  if (await templates.sendTemplate(templateName)) messages.reload();
}
</script>

<template>
  <div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
    <div
      v-for="template in templates.templates"
      :key="template.name"
      class="flex h-56 cursor-pointer flex-col gap-2 rounded-lg border p-3 hover:bg-surface-gray-2"
      @click="send(template.name)"
    >
      <div class="truncate border-b pb-2 text-base-semibold">{{ template.name }}</div>
      <TemplateContent
        class="min-h-0 flex-1 text-sm text-ink-gray-5"
        :header="template.header_text"
        :body="template.message"
        :footer="template.footer"
        :buttons="template.buttons"
        body-class="min-h-0 flex-1 overflow-y-auto"
      />
    </div>
  </div>
</template>
```

`TemplateContent` is the template-side counterpart of `MessageBubble`, and the bubble's own
template branch renders through it — so a preview cannot drift from the message it becomes.
Feed it a `WhatsAppTemplate`'s `header_text`/`message`/`footer` as above, or a sent
`WhatsAppMessage`'s `header`/`template`/`footer`.

`body-class` exists for the fixed-height card above: only the body scrolls, so the footer and
buttons stay pinned rather than being clipped by a long body.

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

`useMessages()` injects, so it must be called during `setup()`.

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
tooltip (`reactedByLabel`), and the input's reply preview. `MessageList`, `MessageBubble` and
`MessageInput` all take both props. There is no `from_name` field and no reactor name on a
reaction — see [Design decisions](#design-decisions).

### Realtime

`useMessages()` resolves the host's **existing** socket.io connection and subscribes to the
app's `whatsapp_message` event, reloading when the event names one of its references. That
covers an inbound message, a status change, and another agent's send.

It never calls frappe-ui's `initSocket()`: that opens a *new* connection, and a second one
alongside the host's would mean duplicate room joins and doubled events. What it reads is the
`$socket` global frappe-ui's own plugin sets, so a host using that plugin needs no extra
wiring.

The app publishes that event to each reference **document's** room rather than site-wide, so
the controller also emits `doc_subscribe` for every reference — the socket server checks read
permission on the document before joining, which is what keeps the event off other users'
connections. The subscriptions follow the reference list when it changes, and are dropped on
effect-scope dispose along with the handler, so a controller held longer than a component is
still cleaned up correctly. Rooms belong to the connection, not to the controller: two
controllers on the same reference share one subscription, and the first to dispose leaves the
room for both.

Expose the socket at your app root with `provide("socket", socket)` (`"$socket"` and an
`app.config.globalProperties.$socket` global are also read). **With no socket the subscription
is skipped entirely** — everything else works, the conversation just refreshes only on the
controller's own writes and on `reload()`.

### Finding rows in the DOM

`MessageList` takes a `rowClass`, applied to every message row, for a host that has to locate
rows itself:

```vue
<MessageList :messages="messages.messages" row-class="activity" />
```

CRM needs this: `Activities.vue` collects `.activity` elements to position its scroll, and
WhatsApp rows have to be among them. The class name is the host's, so it is passed in rather
than baked into the package.

### Exposed methods

`MessageInput` exposes `focus()`, and focuses itself whenever `replyTo` becomes set.

### Where a `class` lands

`MessageInput` sets `inheritAttrs: false` — its template has multiple roots, which Vue cannot
auto-inherit onto at all — and binds `$attrs` onto its input row instead. So a `class` does
land, on the row rather than on the reply preview above it.

`MessageList` inherits attrs normally, so a `class` lands on the list root. It is bound with
explicit props rather than `v-bind="controller"`, which is what makes that safe: spreading the
controller onto it would land the verbs as fall-through attrs and stamp function-valued
attributes into the DOM.

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

## Backend

Requires the `whatsapp` app on the site: the controllers call these whitelisted methods
directly. The components themselves are pure UI and render whatever they are handed, but the
batteries-included path assumes the endpoints are there.

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
`WhatsApp Message.notify_change()` with the reference doctype and docname, on that document's
room.

### Security

The endpoints guard on the **reference document**: every `[doctype, docname]` pair handed to
`get_messages` is checked for existence and `has_permission("read")`, and the write endpoints
check the message and its reference the same way.

The WhatsApp app has **no role model of its own yet** (its open gap
[#10](https://github.com/ps173/frappe-whatsapp/issues/10) — everything else requires System
Manager). So this check is *orthogonal* to a host's role policy, not a superset of it: a host
that gates WhatsApp access by role must keep that gate in front of these endpoints rather than
assume the app's reference check subsumes it.

## Conventions

- `.vue` files are **tab-indented, width 4**, per the repo `.editorconfig`. Prettier runs
  in pre-commit and reads that config, so write tabs.
- `.ts` files are **2-space** — the editorconfig glob does not cover `*.ts`, so prettier's
  default applies.
- No build step and no `tsconfig.json`. The consuming host typechecks this source.

## Design decisions

Three choices that look odd without their reasoning.

**The view model uses the DocType's own fieldnames.** CRM's old endpoint returned a dialect
of its own — `direction` as `type`, `media_url` as `attach`, `whatsapp_template` as
`template`, `status` lowercased — built by popping the real fieldnames off each row. The
renames were undocumented and lossy: `mime_type` never reached the client, and `template`
held a docname in one place and rendered prose in another. This package takes the WhatsApp
app's fieldnames unrenamed, and since the endpoint filling them is now the app's own, the
contract and the query behind it share one vocabulary. Keeping that dialect would have
encoded one host's history into a shared package; a shim to undo it would have been a
translation layer nobody deletes.

A pure DocType shape isn't achievable, and `types.ts` says so rather than pretending:
`reactions[]`, `file_name`/`file_size`, the rendered `template`/`header`/`footer`/`buttons`
and the `reply_*` fields need reaction folding, a `File` join, variable substitution and
linked-document resolution. The interface is split into two labelled groups — **DocType
fields** and **server-derived** — because which group a field is in tells you where to look
when it's wrong.

**Host-specific data arrives as arguments, not hooks.** Two things in the old endpoints
genuinely were CRM-specific. The obvious fix was `frappe.get_hooks` callbacks; both are
better as arguments.

`get_from_name()` was deleted rather than hooked. It reads only the reference
doctype/docname, so across a whole fetch it resolves to *one string* — and the rule it feeds
(outgoing → "You", incoming → the contact) is presentation the client can already decide
from `direction`. A hook would have bought indirection to compute a known constant. It's the
`senderName` prop now, and `from_name`/`reply_to_from` are gone from the wire.

The Deal→Lead union became the `references` argument. A host decides what a conversation
spans; the endpoint checks `has_permission("read")` on every pair it's handed. That's
*stronger* than a hook — a registered resolver is trusted to return a safe scope, an
argument is assumed hostile and checked.

**`frappe-ui` is a peer, never a dependency** — see the section above for the failure mode.
Worth stating plainly because the work started from "add frappe-ui to the whatsapp app" and
the answer was the opposite.

**A note on `FP2`.** `@framework/ui`'s PHILOSOPHY scopes FP2 ("the host owns fetching") to
*list-view controls* — SortBy, Filter, ColumnSettings, QuickFilter. It does not forbid a
composable from fetching, and the closest precedents do exactly that: `useNotifications`
owns a `createListResource`, `useActivityTimeline` a `createResource`. Reading FP2 as a
blanket rule is what kept this package fetch-free for longer than it should have been.

## Not included

- **No emoji picker.** Reactions are a fixed six-emoji bar (`REACTION_EMOJIS`, overridable via
  `reactionEmojis`). Typing emoji is the OS keyboard's job.
- **No i18n.** Every user-facing string is an English-defaulted prop — `placeholder`,
  `youLabel`, `replyLabel`, `emptyLabel`, and so on. Pass your own translations in.
- **No toasts or error dialogs.** Failures are surfaced on the controller's `error`; where an
  app shows errors is the app's decision.
- **No template picker.** `TemplateContent` renders one template; the container, the search
  and the grid are host layout. See [Sending a template](#sending-a-template).
- **No socket of its own.** `useMessages()` uses the host's, via `provide("socket", …)` or a
  `$socket` global; without one, live updates are simply off.
- **No account or settings management.** Choosing the WhatsApp account and enabling the
  channel stay in the host (or the desk UI). Editing templates is desk-side too: point a
  "create a template" affordance at `/app/whatsapp-template/new`, or call the controller's
  `createTemplate()`.

## Types

From `@whatsapp/ui` (or the `./Messages` subpath): `WhatsAppMessage`, `WhatsAppTemplate`,
`WhatsAppReaction`, `WhatsAppTemplateButton`, `WhatsAppDirection`, `WhatsAppStatus`,
`WhatsAppContentType`, `MediaFile`, `MessageReference`, `SendMessagePayload`, `ReactPayload`,
`UseMessagesOptions`, `MessagesController`, `UseTemplatesOptions`, `TemplatesController`,
`SendTemplateOverrides`, `MessageListProps`, `MessageBubbleProps`, `MessageInputProps`,
`TemplateContentProps`, `TemplateButtonsProps`.

The generic helper components live beside them, under `./common`: `MediaPreviewDialogProps`,
`ReactionPickerProps`. `MediaKind` and `MediaAttachment` come from the package root.
