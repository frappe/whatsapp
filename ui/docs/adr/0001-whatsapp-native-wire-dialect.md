# The view model speaks the WhatsApp app's own field names; the host stops renaming

CRM's `get_whatsapp_messages()` (`crm/api/whatsapp.py`) does not return WhatsApp
Message rows — it returns a dialect of its own, built by popping the real
fieldnames off each row and re-adding them under other names: `direction` →
`type`, `media_url` → `attach`, `whatsapp_template` → `template`,
`context_message_id` → `reply_to_message_id`, `reference_docname` →
`reference_name`, `template_body_parameters` → `template_parameters`, plus
`is_template` exploded into a `message_type: "Template" | "Manual"` string *and*
a redundant `use_template` boolean, `mime_type` consumed into a computed
`content_type`, `is_reply` precomputed from the context id, and `status`
lowercased at the boundary. The renames are historical, undocumented, and lossy:
`mime_type` never reaches the client at all, and `template` is later overwritten
with the *rendered* body, so one key means a docname on line 408 and prose on
line 453.

`@whatsapp/ui` takes the WhatsApp app's own DocType fieldnames, unrenamed, as its
contract (`src/components/Messages/types.ts`; the host-facing walkthrough is
[`src/components/Messages/README.md`](../../src/components/Messages/README.md)). The
endpoint that fills it is now the app's own
([ADR-0003](0003-the-app-owns-the-message-api.md)), so the contract and the query
behind it share one vocabulary: `get_messages` selects `WhatsApp Message`
fieldnames and returns them. No layer in between gets the chance to rename them.

A pure DocType shape is not achievable, and the type says so out loud rather than
pretending. `reactions[]`, `file_name`/`file_size`, the rendered
`template`/`header`/`footer`/`buttons`, and the `reply_*` quote fields exist in
no table: they need linked-document resolution, a `File` join, template variable
substitution, and reaction folding — all server-side work. `types.ts` splits the
interface into two labelled groups, **DocType fields** and **server-derived**,
because knowing which group a field is in is what tells you where to go looking
when one is wrong.

## Considered Options

- **Keep CRM's dialect as the package's contract.** Rejected: it encodes one
  host's history into a shared package. Every future host would inherit renames
  that mean nothing to it, and the `template` collision would become permanent
  API rather than a bug to fix.
- **Ship a JS shim in the host that renames CRM's dialect to native names.**
  Rejected: a translation layer nobody ever deletes. It preserves the lossy
  parts (`mime_type` is already gone by then) and leaves two vocabularies alive
  in the same app indefinitely. Deleting the rename block is strictly less code
  than adding a layer to undo it.
- **Invent a neutral third dialect for the library.** Rejected: a shared package
  should minimize the number of names in the world, not add one. The DocType's
  own fieldnames are the one naming anybody can look up.

## Consequences

- **CRM's endpoints are replaced by the app's, not corrected in place (PR-2).**
  There is no rename block left to drop: `whatsapp.whatsapp.api.messages`
  supersedes `crm.api.whatsapp`'s five message endpoints wholesale, and the
  generic halves of them (reaction folding, template rendering, reply resolution,
  the `File` join, `_humanize_error_message`) moved into the app rather than being
  patched. What stays in CRM is the CRM-specific remainder: its role gate, its
  notification hook, and the Deal→Lead reference list it now passes in as an
  argument. See [ADR-0003](0003-the-app-owns-the-message-api.md).
- **`get_from_name()` is deleted, not moved and not hooked.** It reads only the
  reference doctype/docname, so across a whole fetch it resolves to one string,
  and the rule it feeds — outgoing is "You", incoming is the contact — is pure
  presentation. It became the `senderName` prop and left the server entirely; no
  Message carries a `from_name`, and `reply_to_from` is gone with it.
- **`_infer_content_type` does not survive as wire data.** Render kind is
  presentation, so it lives in the library as `contentTypeFromMime()`
  (`src/components/Messages/media.ts`). `get_messages` returns `mime_type` and
  computes no `content_type`; the app's `infer_content_type` in `api/utils.py` is
  the ported sibling of `mime_type_for_content_type` (which the *send* path does
  need) and no endpoint calls it.
- **Status stays Title Case**, matching the DocType's Select
  (`Pending\nSent\nDelivered\nRead\nFailed`, default `Pending`). The tick
  renderer compares against those literals. The status-normalization tests in
  `crm/tests/test_whatsapp.py` go away with the endpoint they cover; the app's
  `api/test_messages.py` is where this contract is now asserted. Note that with
  normalization gone an absent status stays absent rather than becoming `""` —
  the contract has `status` optional.
- **`is_reply` and `use_template` disappear from the wire.** Both are derivable
  client-side (`Boolean(context_message_id)`, `is_template`), and the library
  derives them.
- **`get_sendable_templates()` returns `buttons`.** The picker previews
  header/body/footer/buttons so that what a user picks is what gets sent, but
  `buttons` is the `WhatsApp Template Button` child table and a `frappe.get_all`
  on the parent cannot return one — no field list will do it. The function runs a
  second query grouped back by `parent`, modelled on the `Template Variable` query
  it already ran a few lines above: filter on
  `{"parent": ["in", names], "parenttype": "WhatsApp Template"}`, select
  `button_type`, `button_text`, `url` and `phone_number`, order by `idx`. Without
  it the preview omits the button row — the contract has `WhatsAppTemplate.buttons`
  optional — while the sent bubble *does* show buttons, because that path resolves
  the template through `frappe.get_doc`. Closing that mismatch was the point.
- `error_message` remains a DocType field storing Meta's raw failure payload.
  Reducing it to a human sentence is server work, so `humanize_error_message()`
  ported into `whatsapp/whatsapp/api/utils.py` and `get_messages` applies it —
  the client never sees the raw JSON and has nothing to reduce.
