### WhatsApp

Official WhatsApp integration for Frappe Apps.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench install-app whatsapp
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/whatsapp
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### Features

#### Core Messaging

- Receive incoming messages via Meta webhook (text, buttons, interactive, reactions, images, audio, documents, video, stickers)
- Auto-create WhatsApp Profiles for new contacts
- Send outgoing template, text, media, reaction, and interactive (buttons/lists) messages
- Message status tracking (Sent, Delivered, Read, Failed)
- **Reply-to / context messages** — outgoing messages can reference a previous message ID for threaded conversations via `reply_to_message` Link field
- **Read receipts** — configurable auto-send of `read` status per account (`auto_read_receipts` checkbox on WhatsApp Account)
- **Reaction messages** — send and receive emoji reactions to messages
- **Media messages (non-template)** — attach files (images, documents, videos, audio) as standalone outgoing messages; file is uploaded to Meta at send time
- **Template header media upload** — lazy upload of template header media (images, videos, documents) to Meta on first send, cached for reuse
- **Interactive messages** — quick reply buttons (up to 3) and list messages (up to 10 items) for structured user responses

#### Template Management

- WhatsApp Template management (create, sync, push to Meta)
- Template variables (named and positional)
- Button support (Quick Reply, URL, Copy Code, Phone Number, Voice Call)
- Template status tracking (Pending, Approved, Rejected, Deleted)

#### Client API

Whitelisted endpoints so a host app can build a messaging UI without reimplementing WhatsApp
logic. All of them are host-agnostic — no host's DocTypes or roles appear in their signatures.

| Method | Purpose |
|---|---|
| `whatsapp.whatsapp.api.messages.get_messages(references)` | Messages for one or more reference documents, with reactions folded onto their targets, template bodies rendered, replies resolved, attachment metadata joined and failure payloads reduced to a sentence |
| `whatsapp.whatsapp.api.messages.send_message(to, message, attach, content_type, reply_to, reference_doctype, reference_docname)` | Send text or media, optionally as a reply. Returns the new message's name |
| `whatsapp.whatsapp.api.messages.react_to_message(message, emoji)` | React to a message. Returns the reaction message's name |
| `whatsapp.whatsapp.api.messages.send_template(template, to, reference_doctype, reference_docname)` | Send an approved template |
| `whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.get_sendable_templates(reference_doctype)` | Approved templates whose variables can be resolved from that DocType, buttons included |
| `whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.create_template_and_push(doc_data, account_name)` | Create a template and push it to Meta for approval |

`references` is a JSON list of `[doctype, docname]` pairs — the **host** decides the scope
(e.g. a CRM Deal that should also show its converted Lead's messages), and the endpoint
verifies `read` permission on every reference it is handed. The **first** pair is where a
send attaches; the rest only widen the read.

`to` is a `WhatsApp Profile` name or a raw phone number, resolved against the default
account. `WhatsApp Message.notify_change()` publishes a `whatsapp_message` realtime event
carrying the reference doctype/docname, so a conversation view can refresh itself. It fires on
insert, on delete, and on a status change from the webhook, and is emitted after commit.

The event goes to the **reference document's room**, as `Communication.notify_change()` does,
so a client receives it only after a `doc_subscribe` the socket server has permission-checked.
A message with no reference publishes nothing — there is no room to scope it to, and the
site-room fallback would reach every Desk user.

Sender display names are deliberately **not** returned: for a given conversation the name is a
single string the host already knows, so it is passed to the UI rather than resolved per
message.

Permissions guard on the reference document. The app has no role model of its own yet
(see Known Gaps below), so a host with its own role policy must keep that check in front.

#### Client UI — `@whatsapp/ui`

Shared Vue components for rendering WhatsApp conversations, in [`ui/`](ui/). Ships raw source
consumed by a host's bundler; `frappe-ui` and `vue` are peer dependencies. See
[`ui/README.md`](ui/README.md) to install and use it.

#### Account & Configuration

- Multiple WhatsApp Business Accounts
- Auto-detect account from phone_number_id on webhook
- Default account fallback

#### Notifications & Automation

- 6 built-in Frappe Notifications (message received/sent/failed, status updated, template approved/rejected)
- Append Actions — auto-create linked documents in other DocTypes on incoming/outgoing messages (configurable per account)
- Server Script hooks via standard Frappe lifecycle (after_insert, after_save, etc. on WhatsApp Message)

#### Observability

- Browsable audit log (WhatsApp Log) capturing all webhook events, API calls, template operations, and message sends
- Log levels: Info, Warning, Error, Debug
- HMAC-SHA256 webhook signature verification

### Deferred

These features are planned but not yet implemented:

- **Media download on webhook** — incoming media messages capture only metadata (`media_id`, `mime_type`, `media_url`); the file bytes are never fetched. Pulling them into a Frappe `File` needs an async job plus a realtime update so the form reflects the download.
- **Location messages** — send and receive geographic location data (`latitude`/`longitude`/`name`/`address` fields)
- **Order messages (catalog)** — support `order` webhook type for catalog-based purchases and sending product catalog messages

### Known Gaps (to be fixed)

These are operational issues in the current implementation that should be addressed before a stable public release:

- **[P1] Role-based permissions** — all operations require System Manager. Production deployments need per-role read/write control on `WhatsApp Message`, `WhatsApp Profile`, and `WhatsApp Template` so non-admin users (e.g. support agents) can use the app safely.
- **[P1] App screen / home page** — `add_to_apps_screen` in `hooks.py` is commented out. The app has no dedicated UI entry point in Frappe Desk.
- **[P2] No contact enrichment** — `WhatsApp Profile` only stores phone number and display name. No fetch of Meta profile photo, email, or other contact metadata.
- **[P2] No send scheduling** — messages are sent immediately on submit. No support for delayed or time-zone-aware scheduled sends.
- **[P2] Webhook retry/recovery** — if webhook processing throws mid-way (e.g. after profile created but before message inserted), there is no recovery path. Partial state can be left behind silently.

### Planned

- Tech Provider Based Login Flow
- Bulk Sending
- Catalog Upload + Catalog Based Templates
- Group management
- Calling features
- Auto-block profile after N consecutive failed messages
- WhatsApp Flows (Meta's native form/flow builder)
- CRM chat-style UI in Frappe Desk
- WhatsApp preview for templates in desk

### Design Decisions

See [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) for intentional product constraints (e.g. named-only template variables, reference-DocType-driven parameters).

### License

mit
