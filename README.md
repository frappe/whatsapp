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
- **Collect forms**: send a WhatsApp Flow from a template, and write the customer's answers to a
  document with no code.
- **Build on it**: a small whitelisted API and a Vue component library let a host app such as a
  CRM embed conversations without reimplementing any WhatsApp logic.
- **See what happened**: every webhook, API call and send is recorded in a browsable
  `WA Log`.

## Contents

- [Installation](#installation)
- [Getting Started](#getting-started)
- [Troubleshooting](#troubleshooting)
- [Features](#features)
- [Flows](#flows)
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
   Other fields are delivered but ignored. To use [Flows](#flows), subscribe to `flows` too.

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
| Incoming messages | Text, buttons, interactive replies, reactions, images, audio, documents, video, stickers and Flow responses. |
| Outgoing messages | Template, text, media, reaction, interactive and interactive Flow messages. |
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
- Buttons: Quick Reply, URL, Copy Code, Phone Number, Voice Call and [Flow](#flow-buttons-on-templates).
- Header media (image, video, document) is uploaded to Meta on first send and cached for reuse.
- Status tracking: Pending, Approved, Rejected, Deleted.

### Accounts

- Multiple WhatsApp Business Accounts on one site.
- Incoming webhooks are matched to their account by `phone_number_id`.
- A default account is used when a send does not name one.

### Notifications and automation

- **WhatsApp as a Notification channel:** any Frappe **Notification** can send a WhatsApp
  template. See [WhatsApp notifications](#whatsapp-notifications) below.
- **7 built-in Frappe Notifications:** message received, sent and failed, status updated,
  template approved and rejected, and Flow alert.
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

### Flow forms

- Build Flows visually in the Flow builder, or sync the Flows you build in Meta's Flow Builder.
  Publish, deprecate and edit them in Desk too.
- Add Flow buttons to templates. Fill the form's first screen from the reference document.
- Write the answers to the reference document or to a new document, with no code.
- Read the answers in the conversation, with sensitive answers masked.

See [Flows](#flows).

### Observability

- **WA Log** records every webhook event, API call, template operation and message send.
- HMAC-SHA256 signature verification on every webhook delivery.

## Flows

A WhatsApp Flow is a form that opens inside WhatsApp. The customer fills in one or more screens
and submits. In this app, each Flow is a **WA Flow** document. You build Flows in the
[Flow builder](#flow-builder), or in Meta's Flow Builder in WhatsApp Manager. Either way the Flow
lives on Meta, and the app keeps its WA Flow in step with it.

There are two ways to send a Flow:

- **From a template** with a [Flow button](#flow-buttons-on-templates). This is the usual way, and
  the only one that runs Response actions.
- **As an interactive message** through [`send_flow`](#send_flow), inside the customer service
  window. The app stores and shows the answers, but runs no Response actions.

### Set up Flows

1. In the Meta App Dashboard, open **WhatsApp > Configuration** and subscribe to the `flows`
   webhook field, next to `messages`. The app cannot check this, because Meta's API does not
   report the subscribed fields. **Check Webhook Subscription** does not cover it.
2. Get your business verified on Meta. Meta sends Flows only for a verified business.
3. Sync the Flows:
   - The scheduler syncs the Flows of every active account daily.
   - To sync one account now, open the WA Account in Desk and click **Sync Flows** in the menu.
     The message shows how many Flows were created, updated and removed. From code, call
     `whatsapp.whatsapp.flows.sync.sync_flows(account_name)`.
   - In Desk, **Refresh from Meta** on a WA Flow syncs that one Flow.

A Flow belongs to a WhatsApp Business Account, not to one phone number. A sync records the
business ID on the Flow. When two WA Accounts share a business ID, their templates can use the same
Flows, and a sync from the second account does not move the Flow to it.

A template sync also syncs a Flow that one of its Flow buttons names. A `flows` status event for
an unknown Flow syncs that Flow. A sync removes a Flow that Meta no longer lists. If a template
button links to that Flow, the Flow stays and WA Log gets a Warning.

### WA Flow in Desk

A WA Flow mirrors Meta: the Flow ID, name, account, business ID, **Status** (Draft, Published, Throttled,
Blocked or Deprecated), categories, Flow JSON version, endpoint URI, preview URL and Flow JSON.
The list has no **New** button: create a Flow in the [Flow builder](#flow-builder) or in
WhatsApp Manager.

| Button | Shown when | What it does |
|---|---|---|
| Refresh from Meta | Always | Syncs this Flow again. |
| Publish | Draft | Publishes the Flow on Meta. Disabled while Meta reports validation errors. |
| Deprecate | Published, Throttled or Blocked | Deprecates the Flow on Meta, after you confirm. You cannot undo this. |
| Open preview | A preview URL is set | Opens Meta's preview in a new tab. |

Each action syncs the Flow again after Meta answers. If the form has unsaved changes, the action
asks you to save first.

You can edit the **Flow JSON** while the Flow is Draft or Published. A save uploads the JSON to
Meta. Meta keeps JSON with errors as a draft, so the save succeeds and the form lists Meta's
validation errors with their line and column. An edit to a Published Flow can move it back to
Draft on Meta, and the status follows.

Status changes arrive on the `flows` webhook. Health alerts, version-expiry warnings and a change
to Throttled or Blocked go to WA Log and fire the **WhatsApp Flow Alert** notification.

### Flow builder

The Flow builder is a part of [`@whatsapp/ui`](ui/README.md#the-flow-builder) that a host app
embeds. It follows the layout of Meta's Flows playground: a list of screens and an accordion of
their content on the left, and a WhatsApp phone preview on the right.

- **New flow** asks for a name and categories, and starts blank or as a copy of another Flow. The
  Flow is created on Meta at once.
- **Editing.** Add, reorder and delete screens and content: headings, text, short answers,
  paragraphs, dates, choices, dropdowns, opt-ins, images, photos, documents and links. Each field
  shows Meta's limit as a counter. Under **More**, a question has its answer key, **Hide in chat**
  (sensitive) and **Prefill from template** (first screen only).
- **Navigation.** Each screen's button goes to the next screen in the list, and the last screen
  completes the Flow. The answers of every question are sent on completion, under their answer
  keys. A Flow whose JSON navigates in another way keeps that navigation, read only.
- **Saving.** The builder saves by itself after each pause in editing. A save uploads the Flow JSON
  to Meta, and Meta's validation errors show on the rows they belong to.
- **Publish** confirms first, because Meta does not allow edits after publishing. Published,
  Throttled, Blocked and Deprecated Flows open read only, with **Make a copy**.
- **Preview.** The phone shows the selected screen. **Interactive mode** lets you fill the Flow in
  and go through its screens. **Copy Flow JSON** and **Edit JSON** give the full JSON.
- Anything the builder does not edit is kept exactly as written and shown as an **Advanced
  block**.

| Method (`whatsapp.whatsapp.flows.…`) | Permission | What it does |
|---|---|---|
| `builder_reads.get_flow_list` | read WA Flow | The Flows, with how many templates use each. |
| `builder_reads.get_flow_for_builder` | read WA Flow | One Flow, with the templates that map each answer key. |
| `authoring.create_flow` | create WA Flow | Creates a Flow on Meta, blank or as a copy. |
| `authoring.save_flow` | write WA Flow | Saves and uploads a Draft. Refuses when the Flow changed since it was opened. |
| `authoring.copy_flow` | create WA Flow | Copies a Flow on Meta as a new draft. |
| `authoring.delete_flow` | write WA Flow | Deletes a Draft, unless a template uses it. |
| `manage.publish_flow` | write WA Flow | Publishes a Flow. |

### Flow buttons on templates

Add a button of type **Flow** to a WA Template, next to its other buttons. A template can have
more than one Flow button. The label can have at most 25 characters.

| Field | Details |
|---|---|
| Flow | The WA Flow that the button opens. It must belong to the WhatsApp Business Account of the template's account, and must not be Deprecated. |
| Flow Screen | The screen the Flow opens on. It must be an entry screen. Blank means the first entry screen. |
| Flow Icon | Document, Promotion or Review. Optional. |
| Flow Action | Navigate (the default), or Data Exchange for a Flow that calls your own endpoint. |
| Flow Inputs | The data the first screen starts with. See below. |
| Response Actions | What to do with the answers. See below. |

Flow Inputs and Response Actions are JSON fields on the button row. The template form in
`@whatsapp/ui` edits them with pickers, so nobody types a key. Meta does not store them, so a
template sync keeps them.

A send of a template with a Blocked or Deprecated Flow fails before Meta is called. Meta refuses
a Throttled Flow after ten sends an hour. Both give a Failed message with the reason.

#### Flow inputs

Flow inputs fill the first screen from fields of the template's reference document, for example
the customer's name:

```json
[{"key": "customer_name", "source_field": "first_name"}]
```

The entry screen must declare each `key` in its `data`, as a string, number or boolean. The
template must have a reference DocType. A message from such a template must have a reference
document of that DocType, or the message is refused. This applies to every send path:
`send_template`, the Notification channel and a direct insert. At send time, each value is converted to its declared
type. An empty field is left out, because Flows refuse `null`.

#### Response actions

A Response action updates the reference document or creates a document from the answers:

```json
[
  {
    "action": "Update Reference",
    "condition": "response.outcome == 'interested'",
    "fields": [{"source": "next_step", "target_field": "next_step"}]
  },
  {
    "action": "Create Document",
    "doctype": "Deal Feedback",
    "fields": [
      {"source": "rating", "target_field": "rating"},
      {"source": "reference_name", "target_field": "deal"},
      {"source": "whole_response", "target_field": "answers"}
    ]
  }
]
```

- **`condition`** is an optional Python expression, evaluated with Frappe's safe evaluator. It
  can use `response` (the answers), `doc` (the reference document's values, or `None`) and
  `message` (the incoming WA Message's values). All three are plain data with attribute access,
  not documents, so a condition cannot call `db_set` or other document methods. A condition that
  fails to evaluate is logged as an Error, and its action is skipped.
- **`source`** is an answer key from the Flow, a dotted path into a nested answer such as
  `address.city`, or a message source: `sender_phone`, `sender_name`, `reference_doctype`,
  `reference_name`, `received_at` or `whole_response` (all the answers as JSON).
- **`target_field`** is a field on the reference DocType (Update Reference) or on `doctype`
  (Create Document). A save refuses a field whose type cannot hold the source. If the current
  Flow version no longer sends a source, the save shows a warning only, because older versions
  still answer.

Values are converted by the type of the target field:

| Target field | Value |
|---|---|
| Check | A boolean, or the string `"true"` or `"false"`. |
| Int, Float, Currency, Percent | A number. Int refuses a number that is not whole. |
| Date, Datetime | An ISO 8601 string. A time with a zone is converted to the system time zone. |
| Table MultiSelect | A list, one row per item. |
| Data, text fields, Select, Link, Phone | A list joined with ", ". An object as JSON. |
| JSON, Code | An object or a list as JSON. |
| Attach, Attach Image | Skipped with a Warning. See [Limitations](#limitations). |

The actions run in their configured order, as the system with `ignore_permissions`. Each action
logs its result to WA Log against the message.

Because the actions skip permission checks, a template save checks the permissions of the user who
saves it:

- Create Document needs `create` permission on `doctype`.
- Update Reference needs `write` permission on the template's reference DocType.
- Each target field above permission level 0 needs `write` access to its permission level.

The check runs on every save. If a user with fewer permissions edits the template later, the save
checks their permissions. A template sync from Meta skips the check.

- A missing answer, or one that is `null`, is skipped. It is never written as empty.
- A value that cannot be converted skips that field, with a Warning.
- A failed action is rolled back and logged as an Error. The next action still runs, and the
  stored response is never lost.

### Receiving responses

A completed Flow arrives on the `messages` webhook. The app stores the answers in **Flow
Response** (`flow_response`) on a new incoming WA Message. The message text is a one-line
summary of the labelled answers.

The app then finds the message that sent the Flow:

1. By the **Flow token**. Every Flow send carries a random token, and Meta returns it with the
   answers.
2. Else by the **reply context**, the ID of the message the response answers. Some iOS clients
   drop the token.

A matched response inherits the send's reference document, so it lands on the record that sent
the form, even when another record has the same phone number. It also gets the send's `flow` and
`flow_template`, and `reply_to_message` points at the send. Then the button's Response actions run.

A response that matches no send, for example to a Flow sent from WhatsApp Manager, is stored and
shown. Its `flow` is empty, it goes through Append Actions like any incoming message, and it runs
no Response actions. Its message text is "Form submitted", not a summary of the answers.

A response to a template with several Flow buttons that lost its token keeps the template, but
not its Flow. It runs no Response actions, and WA Log gets a Warning.

A Flow marks an answer as sensitive in a screen's `sensitive` list. Password and passcode text
inputs are always sensitive. The conversation shows a sensitive answer as masked, and the summary leaves
it out. When the response knows its template but not its Flow, every key that any Flow button of
the template marks as sensitive is masked.

`flow_response` has permission level 1, and only System Manager can read that level. Other Desk
and REST users do not get the raw answers. Server code, such as Response actions and
`get_messages`, reads them without permission checks.

### Automation without code

| Tool | Set up |
|---|---|
| Notification | **Document Type** WA Message, **Send Alert On** Method, **Method** `on_flow_response`. Fires for every Flow response, after the Response actions. |
| Webhook (core DocType) | **DocType** WA Message, **Doc Event** `on_submit`, **Condition** `doc.flow_response`. Sends the answers to an external URL. Add `flow_response`, `reference_doctype` and `reference_docname` to the request data. |
| WhatsApp Flow Alert | Built in. A System Notification to System Manager when a Flow health alert starts, a Flow version nears expiry, or a Flow becomes Throttled or Blocked. |

WA Flow also fires `on_flow_status_change` when its status changes.

### Server Scripts

A Server Script on WA Message with **DocType Event** After Submit runs after the Response actions,
so it sees their writes. It runs as Guest, because the webhook request has no session. Writes to
other documents need `ignore_permissions`.

This script gives the deal owner a ToDo when a customer rates a deal 1 or 2:

```python
if doc.flow_response and doc.reference_doctype == "CRM Deal":
	answers = json.loads(doc.flow_response)
	if answers.get("rating") in ("1", "2"):
		frappe.get_doc({
			"doctype": "ToDo",
			"description": "Low rating: " + (answers.get("comment") or ""),
			"reference_type": doc.reference_doctype,
			"reference_name": doc.reference_docname,
			"allocated_to": frappe.db.get_value("CRM Deal", doc.reference_docname, "deal_owner"),
		}).insert(ignore_permissions=True)
```

### Limitations

- **Unverified Meta contract.** Meta's docs contradict themselves or are silent on these points.
  A live test against Meta has not run yet. Each point lives in one place:

  | Point | Code |
  |---|---|
  | The button's `sub_type` is `"flow"` | `FLOW_BUTTON_SUB_TYPE` in `flows/send.py` |
  | The button's `index` is a string | `_button_index` in `flows/send.py` |
  | An interactive message's `data` is a JSON string | `_interactive_data` in `flows/send.py` |
  | `flow_message_version` is `"3"` | `FLOW_MESSAGE_VERSION` in `flows/send.py` |
  | `navigate_screen` is sent only when set | `_navigate_screen` in `flows/template_button.py` |
  | The icon values, sent only when set | `FLOW_ICONS` and `_icon` in `flows/template_button.py` |
  | A response without a token belongs to the template's only Flow button | `FlowResponse._button_index` in `flows/receive.py` |

- **Media answers** from a photo or document picker are stored as Meta's media IDs, but the files
  are not downloaded. A Response action skips an Attach target with a Warning.
- **Responses with no matched send are not masked.** Without the Flow, the app does not know
  which answers are sensitive. The message text is "Form submitted", but the conversation shows
  every answer.
- **Raw answers.** `flow_response` on the WA Message holds every answer unmasked. A System Manager
  in Desk, and a Webhook that sends `flow_response`, see sensitive values.
- **No Flow data endpoint.** Hosting a data endpoint for Flows is out of scope. Flows that call
  your own endpoint still work.

## Client API

Whitelisted endpoints that let a host app build a messaging UI without reimplementing WhatsApp
logic. They are host-agnostic: no host's DocTypes or roles appear in their signatures.

| Endpoint | What it does |
|---|---|
| [`get_messages`](#get_messages) | Read the conversation attached to one or more documents. |
| [`send_message`](#send_message) | Send text or media. |
| [`send_template`](#send_template) | Send an approved template. |
| [`send_flow`](#send_flow) | Send a Flow as an interactive message. |
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

Flow messages carry these extra fields:

| Field | On | Value |
|---|---|---|
| `flow`, `flow_name` | A message with a Flow: an interactive Flow send, or a matched response | The WA Flow name (Meta's Flow ID) and the Flow's display name. |
| `flow_cta` | An interactive Flow send | The button text the contact saw. |
| `flow_answers` | Every Flow response | `[{key, label, value, masked}]`, in the Flow's order. A masked `value` is `null`. Other values are the raw JSON values. |
| `buttons[]` `flow_icon` | A template's Flow button | The button's icon. |

`flow_response` itself is never returned, so a sensitive value never reaches the client.

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

### `send_flow`

```
whatsapp.whatsapp.api.messages.send_flow(flow, to, body, cta, screen, data, mode, reference_doctype, reference_docname)
```

| Parameter | Description |
|---|---|
| `flow` | The `WA Flow` name, which is Meta's Flow ID. |
| `to` | As in `send_message`. |
| `body` | The message text. Required. |
| `cta` | The button text. `Open` by default. |
| `screen` | Optional entry screen. Defaults to the Flow's first entry screen. |
| `data` | Optional JSON object, as a string, for the first screen's data. |
| `mode` | `published` by default. `draft` sends a Draft Flow, to test it. |
| `reference_doctype`, `reference_docname` | Optional document the message belongs to. |

Returns the new message's name. Throws before a message is created if the Flow is Blocked or
Deprecated, if it is a Draft and `mode` is not `draft`, or if `screen` is not an entry screen.
The send works only inside the customer service window. Its responses run no Response actions.

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
and has no variables. A Flow button also carries its `flow_icon`.

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
dependencies. See [`ui/README.md`](ui/README.md) to install and use it. Its Flow parts,
`FlowButtonEditor` and `FlowAnswers`, are described there too.

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
| P2 | Media download on webhook | Incoming media keeps only metadata (`media_id`, `mime_type`, `media_url`); the file is never fetched. Pulling it into a Frappe `File` needs a background job plus a realtime update so the form reflects the download. Flow uploads (photos and documents) need it too. |
| P2 | Manual "Mark as read" | Read receipts are automatic per account only. Add a button to mark a single incoming message as read. |
| P2 | Send scheduling | Messages are sent immediately on submit. No delayed or time-zone-aware sends. |
| P2 | Contact enrichment | `WA Profile` stores only the phone number and display name. No profile photo or other contact metadata from Meta. |
| P3 | Location messages | Send and receive `latitude`, `longitude`, `name` and `address`. |
| P3 | Order and catalog messages | Handle the `order` webhook type, send product catalog messages, upload catalogs to Meta and create catalog-based templates. |
| P3 | Bulk sending | Send one template to many recipients. |
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
