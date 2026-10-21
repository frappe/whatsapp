# WhatsApp

Official WhatsApp integration for Frappe apps, built on Meta's WhatsApp Business Cloud API.

Install it on a site and you can:

- **Receive** messages from customers through a Meta webhook. Each message becomes a
  `WA Message` record and each new sender a `WA Profile`.
- **Send** text, media, reactions, interactive buttons/lists and approved templates, from Desk or
  from code, and watch the status move through Sent, Delivered and Read.
- **Manage templates**: create them in Desk, push them to Meta for approval, and keep them in
  sync daily.
- **Notify over WhatsApp**: WhatsApp becomes a channel in Frappe's Notification, so any document
  event can message a customer with no code.
- **Build on it**: a small whitelisted API and a Vue component library let a host app such as a
  CRM embed conversations without reimplementing any WhatsApp logic.
- **See what happened**: every webhook, API call and send is recorded in a browsable
  `WA Log`.

## Contents

- [Installation](#installation)
- [Getting Started](#getting-started)
- [Troubleshooting](#troubleshooting)
- [Features](#features)
- [Client API](#client-api)
- [Client UI](#client-ui)
- [Planned](#planned)
- [Contributing](#contributing)
- [License](#license)

## Installation

Install with the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench install-app whatsapp
```

## Getting Started

Six steps take a fresh site from nothing to a first message. Everything the app does along the
way is recorded in **WA Log**, so keep it open beside Desk while you go.

### 1. Set up the Meta side

1. At [developers.facebook.com](https://developers.facebook.com/apps) create an app of type
   **Business** and add the **WhatsApp** product to it.
2. Open **WhatsApp > API Setup** and note three values: the **App ID**, the **WhatsApp Business
   Account ID** and the **Phone Number ID**.
3. Generate a permanent access token. The token shown on API Setup expires in 24 hours, so go to
   **Meta Business Settings > Users > System Users** instead: create a system user, assign it
   the WhatsApp app and the business account, and generate a token with the
   `whatsapp_business_messaging` and `whatsapp_business_management` permissions.

> [!NOTE]
> Until the phone number is live, Meta only delivers to numbers you add under
> **API Setup > To**. Sends to anyone else fail with "Recipient phone number not in allowed list".

### 2. Fill in WA Settings

Open **WA Settings** in Desk.

| Field | Value |
|---|---|
| Webhook Verify Token | Any string you choose. You repeat it on Meta in the next step. |
| Webhook Secret | The **App Secret** from the app's **App Settings > Basic** page. Every webhook delivery is checked against it with HMAC-SHA256. If left blank, deliveries are accepted unverified. |
| API Url | Defaults to `https://graph.facebook.com`. |
| API Version | Defaults to `v23.0`. |

Leave **Default Account** empty for now. The first account you create fills it in.

### 3. Register the webhook on Meta

In the app's **WhatsApp > Configuration** page:

1. Set the **Callback URL** to:

   ```
   https://<your-site>/api/method/whatsapp.whatsapp.webhook.handler
   ```

2. Set the **Verify token** to the value from step 2 and click **Verify and save**. The app
   answers Meta's challenge and writes "Webhook verified successfully" to WA Log.
3. Under **Webhook fields**, subscribe to `messages` and `message_template_status_update`.
   Other fields are delivered but ignored.

The site must be reachable over HTTPS from the internet. For a local bench, put a tunnel such as
ngrok in front of it and use the tunnel's URL.

### 4. Create a WA Account

Open **WA Account > New** and fill in:

| Field | Value |
|---|---|
| Account name | Any label. |
| Status | Active. |
| App ID | From step 1. |
| Business ID | The WhatsApp Business Account ID from step 1. |
| Phone ID | The Phone Number ID from step 1. |
| Access token | The system user token from step 1. Hidden after save. |

- The first account saved becomes the **Default Account** in WA Settings. Later accounts
  leave that choice alone.
- **Auto Send Read Receipts** marks incoming messages as read on WhatsApp as they arrive.
- **Append Actions** is optional automation, covered under
  [Notifications and automation](#notifications-and-automation).

Verifying the webhook in step 3 does not subscribe your app to the business account, and Meta
sends no events until it is. After saving, use **⋯ > Check Webhook Subscription** on the account
form. It asks Meta which apps are subscribed and offers a **Subscribe** button if yours is not.

### 5. Sync templates

- **One active account:** the scheduler pulls templates from Meta daily. Nothing to do.
- **Several active accounts:** the daily job only logs that it found more than one. Sync each by
  hand: open the **WA Template** list, click **Sync from Meta** and pick the account.

Each template arrives with its Meta status, and only **Approved** templates can be sent.

### 6. Send a first message

WhatsApp only delivers free-form text inside its **customer service window**: the 24 hours after
the contact last messaged you. Outside that window, which includes a contact you have never
heard from, only an approved template gets through. So the first message to a new contact is a
template.

- **From Desk:** open **WA Message > New** and pick the recipient in **To**. This is a
  WA Profile, created automatically for every sender that has messaged you, or by hand
  with a phone number. Tick **Is Template**, choose a template and **Submit**. The send happens
  on submit, and **Status** moves from Pending to Sent, then to Delivered and Read as Meta's
  status webhooks arrive.
- **From code:** call [`send_template`](#send_template) or [`send_message`](#send_message). Both
  accept a raw phone number for `to` and create the profile if needed.

Reply from the phone and the message lands as an incoming **WA Message** within a few
seconds. The window is now open, and plain text sends work for the next 24 hours.

## Troubleshooting

Start with **WA Log**. Every entry carries a **Level** (Info, Warning, Error, Debug) and an
**Event Type** (Webhook, Template, Message, API, System), and API entries keep the request and
response payloads. Filtering the list on Level = Error is usually the fastest way to the cause.

| Symptom | Cause and fix |
|---|---|
| Meta reports the callback URL could not be verified | The verify token on Meta differs from **Webhook Verify Token** in WA Settings, or the URL is wrong. The response was a 403 "token mismatch" or "invalid request"; check the log entry of type Webhook. |
| Log shows "HMAC signature verification failed" on every delivery | **Webhook Secret** does not match the app's App Secret. Copy it again from **App Settings > Basic**. |
| Sends fail with "Recipient phone number not in allowed list" | The number is live only for test recipients. Add the recipient on **API Setup > To**, or complete Meta's business verification to go live. |
| A text message fails but templates work | The customer service window is closed. Send a template and wait for a reply. |
| Nothing arrives when the phone sends a message | The app is not subscribed to the business account (run **Check Webhook Subscription** on the account), the `messages` webhook field is not subscribed, or the site is not reachable from Meta. Every delivery that reaches the site writes a "Webhook payload received" log entry. |

## Features

### Messaging

| Capability | Details |
|---|---|
| Incoming messages | Text, buttons, interactive replies, reactions, images, audio, documents, video and stickers. |
| Outgoing messages | Template, text, media, reaction and interactive messages. |
| Status tracking | Sent, Delivered, Read and Failed, updated from Meta's status webhooks. |
| Profiles | A `WA Profile` is created automatically for every new contact. |
| Replies | An outgoing message can quote an earlier one through the `reply_to_message` field. |
| Reactions | Send and receive emoji reactions. |
| Read receipts | Optional per account: tick **Auto Send Read Receipts** on the WA Account. |
| Media | Attach an image, document, video or audio file to an outgoing message. It is uploaded to Meta at send time. |
| Interactive | Quick reply buttons (up to 3) and list messages (up to 10 items). |

### Templates

- Create templates in Desk and push them to Meta for approval, or sync existing ones from Meta.
- Named variables using `{{variable_name}}`, resolved from a reference DocType. Positional
  variables (`{{1}}`) are kept on templates synced from Meta but cannot be authored here. See
  [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) for why.
- Buttons: Quick Reply, URL, Copy Code, Phone Number and Voice Call.
- Header media (image, video, document) is uploaded to Meta on first send and cached for reuse.
- Status tracking: Pending, Approved, Rejected, Deleted.

### Accounts

- Multiple WhatsApp Business Accounts on one site.
- Incoming webhooks are matched to their account by `phone_number_id`.
- A default account is used when a send does not name one.

### Notifications and automation

- **WhatsApp as a Notification channel:** any Frappe **Notification** can send a WhatsApp
  template. See [WhatsApp notifications](#whatsapp-notifications) below.
- **6 built-in Frappe Notifications:** message received, sent and failed, status updated,
  template approved and rejected.
- **Append Actions:** automatically create a linked document in another DocType when a message
  comes in, goes out, or both. Configured per account.
- **Server Scripts:** `WA Message` runs the standard Frappe lifecycle (`after_insert`,
  `on_update` and so on), so a Server Script can hook into it.

#### WhatsApp notifications

Installing the app adds **WhatsApp** to the **Channel** options of Frappe's Notification, next to
Email, Slack and System Notification. A rule such as "when a Sales Order is submitted, message
the customer" then needs no code:

1. Open **Notification > New**, set **Channel** to **WhatsApp** and pick the **Document Type**
   and event as usual.
2. Choose a **WA Template**. It must be **Approved**, and if it has variables its
   reference DocType must be the notification's Document Type, since that document fills them.
3. Optionally choose a **WA Account**. Blank uses the default account.
4. Add **Recipients** by document field or by role. A document field must hold a phone number;
   the owner and role recipients use each user's **Mobile No**.

Each recipient gets the template as a regular outgoing `WA Message` linked to the
triggering document, sent from a background job after the transaction commits. The message body
comes from the template, so the notification's own Message field is hidden for this channel. A
failed send is written to WA Log and does not block the document.

### Observability

- **WA Log** records every webhook event, API call, template operation and message send.
- HMAC-SHA256 signature verification on every webhook delivery.

## Client API

Whitelisted endpoints that let a host app build a messaging UI without reimplementing WhatsApp
logic. They are host-agnostic: no host's DocTypes or roles appear in their signatures.

| Endpoint | What it does |
|---|---|
| [`get_messages`](#get_messages) | Read the conversation attached to one or more documents. |
| [`send_message`](#send_message) | Send text or media. |
| [`send_template`](#send_template) | Send an approved template. |
| [`react_to_message`](#react_to_message) | React to a message with an emoji. |
| [`get_sendable_templates`](#get_sendable_templates) | List the templates that can be sent from a DocType. |
| [`create_template_and_push`](#create_template_and_push) | Create a template and submit it to Meta. |

The message endpoints live in `whatsapp.whatsapp.api.messages`. The template endpoints live in
`whatsapp.whatsapp.doctype.wa_template.wa_template`.

```js
const name = await frappe.xcall("whatsapp.whatsapp.api.messages.send_message", {
	to: "+919876543210",
	message: "Your order has shipped.",
	reference_doctype: "CRM Deal",
	reference_docname: "CRM-DEAL-0001",
});
```

### `get_messages`

```
whatsapp.whatsapp.api.messages.get_messages(references)
```

| Parameter | Description |
|---|---|
| `references` | JSON list of `[doctype, docname]` pairs, for example `[["CRM Deal", "CRM-DEAL-0001"], ["CRM Lead", "CRM-LEAD-0007"]]`. |

Returns the messages attached to those documents, oldest first, ready to render:

- reactions are folded onto the message they target,
- template bodies are rendered with their parameters,
- replies are resolved to the message they quote,
- attachment metadata is joined in,
- Meta's failure payloads are reduced to a readable sentence.

The **host** decides what a conversation is. A CRM Deal can also show its converted Lead's
messages by passing both references. The endpoint checks `read` permission on every reference
it is handed.

Sender display names are deliberately not returned. For a given conversation the name is a
single string the host already knows, so the host passes it to the UI instead of having it
resolved per message.

### `send_message`

```
whatsapp.whatsapp.api.messages.send_message(to, message, attach, content_type, reply_to, reference_doctype, reference_docname)
```

| Parameter | Description |
|---|---|
| `to` | A `WA Profile` name or a raw phone number. A missing profile is created. Resolved against the default account. |
| `message` | The text, or the caption when `attach` is set. |
| `attach` | Optional `file_url` of an existing Frappe `File` to send as media. |
| `content_type` | `text` by default. With `attach`, one of `image`, `document`, `audio` or `video`. |
| `reply_to` | Optional name of the `WA Message` to quote. |
| `reference_doctype`, `reference_docname` | Optional document the message belongs to. |

Returns the new message's name. Throws if both `message` and `attach` are empty.

### `send_template`

```
whatsapp.whatsapp.api.messages.send_template(template, to, reference_doctype, reference_docname)
```

Sends an approved template and returns the new message's name. `to` and the reference
parameters behave as in `send_message`. The template's variables are resolved from the
reference document.

### `react_to_message`

```
whatsapp.whatsapp.api.messages.react_to_message(message, emoji)
```

Reacts to the `WA Message` named `message` and returns the reaction's name. A reaction is
its own message document, which `get_messages` folds back onto its target.

### `get_sendable_templates`

```
whatsapp.whatsapp.doctype.wa_template.wa_template.get_sendable_templates(reference_doctype)
```

Returns the approved templates that can be sent from that DocType, with their buttons and
variable mappings. A template qualifies when it is bound to the DocType, or when it is unbound
and has no variables.

### `create_template_and_push`

```
whatsapp.whatsapp.doctype.wa_template.wa_template.create_template_and_push(doc_data, account_name)
```

Creates a `WA Template` from `doc_data`, or updates an existing one that has not been
pushed yet, and submits it to Meta for approval under `account_name`.

### Realtime updates

`WA Message` publishes a `whatsapp_message` realtime event carrying the reference doctype
and docname, so a conversation view can refresh itself. It fires on insert, on delete and on a
status change from the webhook, and is emitted after commit.

The event goes to the **reference document's room**, as `Communication.notify_change()` does. A
client receives it only after a `doc_subscribe` that the socket server has permission-checked.
A message with no reference publishes nothing: there is no room to scope it to, and the
site-room fallback would reach every Desk user.

### Permissions

Every endpoint checks permission on the reference document. The app has no role model of its
own yet (see [Planned](#planned)), so a host that gates WhatsApp access by role registers a
guard in its `hooks.py`. Each guard runs at the start of every endpoint and throws to deny.

```python
whatsapp_access_guard = ["my_app.api.whatsapp.validate_access"]
```

## Client UI

`@whatsapp/ui` is a set of Vue components for rendering WhatsApp conversations, in [`ui/`](ui/).
It ships raw source consumed by the host's bundler, with `frappe-ui` and `vue` as peer
dependencies. See [`ui/README.md`](ui/README.md) to install and use it.

## Planned

Not implemented yet. **P1** items should land before a stable public release.

### Access and reliability

| Priority | Item | Details |
|---|---|---|
| P1 | Role-based permissions | Every DocType is System Manager only. Support agents and other non-admin users need per-role read/write on `WA Message`, `WA Profile` and `WA Template`. |
| P1 | App screen entry | `add_to_apps_screen` in `hooks.py` is commented out, so the app has no entry point of its own in Desk. |
| P2 | Webhook retry and recovery | If webhook processing throws midway, for example after the profile is created but before the message is inserted, partial state is left behind with no recovery path. |
| P2 | Auto-block failing profiles | Block a profile after N consecutive failed messages. |

### Messaging

| Priority | Item | Details |
|---|---|---|
| P2 | Media download on webhook | Incoming media keeps only metadata (`media_id`, `mime_type`, `media_url`); the file is never fetched. Pulling it into a Frappe `File` needs a background job plus a realtime update so the form reflects the download. |
| P2 | Manual "Mark as read" | Read receipts are automatic per account only. Add a button to mark a single incoming message as read. |
| P2 | Send scheduling | Messages are sent immediately on submit. No delayed or time-zone-aware sends. |
| P2 | Contact enrichment | `WA Profile` stores only the phone number and display name. No profile photo or other contact metadata from Meta. |
| P3 | Location messages | Send and receive `latitude`, `longitude`, `name` and `address`. |
| P3 | Order and catalog messages | Handle the `order` webhook type, send product catalog messages, upload catalogs to Meta and create catalog-based templates. |
| P3 | Bulk sending | Send one template to many recipients. |
| P3 | WhatsApp Flows | Meta's native form and flow builder. Large enough to be evaluated on its own. |
| P3 | Groups and polls | Group and community management, and polling. |
| P3 | Calling | WhatsApp Business calling features. |

### Platform and UI

| Priority | Item | Details |
|---|---|---|
| P3 | Tech Provider login flow | Onboard an account through Meta's embedded signup instead of copying IDs and tokens by hand. |
| P3 | Chat UI in Desk | A chat-style conversation view inside Frappe Desk. |
| P3 | Template preview in Desk | A live mobile-style preview of how a template will look on WhatsApp. |

## Contributing

This app uses `pre-commit` for formatting and linting with ruff, eslint, prettier and pyupgrade.
[Install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/whatsapp
pre-commit install
```

[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) documents intentional product constraints, such as
named-only template variables and reference-DocType-driven parameters. Read it before reporting
one of them as a bug.

## License

MIT
