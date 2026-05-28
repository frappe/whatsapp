### Whatsapp

> [!WARNING]
> WIP 🚧: Not meant for use yet!

Official whatsapp integration for frappe crm

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
- **Read receipts** — configurable auto-send of `read` status per account (`auto_read_receipts` checkbox on Whatsapp Account)
- **Reaction messages** — send and receive emoji reactions to messages
- **Media messages (non-template)** — attach files (images, documents, videos, audio) as standalone outgoing messages; file is uploaded to Meta at send time
- **Template header media upload** — lazy upload of template header media (images, videos, documents) to Meta on first send, cached for reuse
- **Interactive messages** — quick reply buttons (up to 3) and list messages (up to 10 items) for structured user responses

#### Template Management
- WhatsApp Template management (create, sync, push to Meta)
- Template variables (named and positional)
- Button support (QUICK_REPLY, URL, COPY_CODE, PHONE_NUMBER, VOICE_CALL)
- Template status tracking (PENDING, APPROVED, REJECTED, DELETED)

#### Account & Configuration
- Multiple WhatsApp Business Accounts
- Auto-detect account from phone_number_id on webhook
- Default account fallback

#### Notifications & Automation
- 6 built-in Frappe Notifications (message received/sent/failed, status updated, template approved/rejected)
- Append Actions — auto-create linked documents in other DocTypes on incoming/outgoing messages (configurable per account)
- Server Script hooks via standard Frappe lifecycle (after_insert, after_save, etc. on Whatsapp Message)

#### Observability
- Browsable audit log (Whatsapp Log) capturing all webhook events, API calls, template operations, and message sends
- Log levels: Info, Warning, Error, Debug
- HMAC-SHA256 webhook signature verification

### Need to test
Webhook related features

### Deferred (tracked as GitHub Issues)

These features are planned but not yet implemented. They are tracked as GitHub issues for better visibility:

- **[#5](https://github.com/ps173/frappe-whatsapp/issues/5) Media download on webhook** — download media from Meta and attach to `Whatsapp Message` / `File` doctype for local access (needs async job + realtime UI update pattern)
- **[#6](https://github.com/ps173/frappe-whatsapp/issues/6) Location messages** — send and receive geographic location data (`latitude`/`longitude`/`name`/`address` fields)
- **[#7](https://github.com/ps173/frappe-whatsapp/issues/7) Order messages (catalog)** — support `order` webhook type for catalog-based purchases and sending product catalog messages

### Known Gaps (to be fixed)

These are operational issues in the current implementation that should be addressed before a stable public release:

- **[P1] [#10](https://github.com/ps173/frappe-whatsapp/issues/10) Role-based permissions** — all operations require System Manager. Production deployments need per-role read/write control on `Whatsapp Message`, `Whatsapp Profile`, and `Whatsapp Template` so non-admin users (e.g. support agents) can use the app safely.
- **[P1] [#11](https://github.com/ps173/frappe-whatsapp/issues/11) App screen / home page** — `add_to_apps_screen` in `hooks.py` is commented out. The app has no dedicated UI entry point in Frappe Desk.
- **[P2] [#12](https://github.com/ps173/frappe-whatsapp/issues/12) No contact enrichment** — `Whatsapp Profile` only stores phone number and display name. No fetch of Meta profile photo, email, or other contact metadata.
- **[P2] [#13](https://github.com/ps173/frappe-whatsapp/issues/13) No send scheduling** — messages are sent immediately on submit. No support for delayed or time-zone-aware scheduled sends.
- **[P2] [#14](https://github.com/ps173/frappe-whatsapp/issues/14) Webhook retry/recovery** — if webhook processing throws mid-way (e.g. after profile created but before message inserted), there is no recovery path. Partial state can be left behind silently.
- **[P3] [#15](https://github.com/ps173/frappe-whatsapp/issues/15) No message thread / conversation UI** — messages between a profile are flat `Whatsapp Message` list docs. No chat-style thread view grouping them by conversation.

### Planned

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
