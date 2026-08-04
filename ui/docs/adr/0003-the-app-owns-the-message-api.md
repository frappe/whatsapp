# The app owns the message API; host-specific data arrives as arguments, not hooks

The five endpoints that back a WhatsApp conversation — read the messages, send one, react,
send a template, list sendable templates — lived only in `crm/api/whatsapp.py`, and almost
nothing in them was about CRM. Folding reaction rows onto their targets, substituting
template variables, resolving a reply's quote, joining `File` for an attachment's name and
size, reducing Meta's stored failure payload to a sentence: every one is a fact about
`WhatsApp Message`, and a second host would have reimplemented all of it. The app now ships
them itself, in `whatsapp/whatsapp/api/messages.py` plus `get_sendable_templates` alongside
the other template methods, and `@whatsapp/ui`'s composables call them directly. Two things
in them genuinely were host-specific, and how those left is the decision worth recording.

**`get_from_name()` became a prop.** The obvious move was a `frappe.get_hooks` callback:
let each host register a resolver and have `get_messages` call it. That was wrong, because
the dependency was never per-message. `get_from_name` reads only `reference_doctype` /
`reference_docname`, fixed for the whole fetch, so across an entire conversation it
resolves to **one string** — and the rule it feeds, outgoing is "You" and incoming is the
contact, is pure presentation decided from `direction`, which the client already has. So it
left the server entirely as the `senderName` prop, and `from_name` and `reply_to_from` are
gone from the wire. A hook would have bought indirection to compute a known constant.

**The Deal→Lead union became the `references` argument.** CRM shows a Deal's messages
together with those of the Lead it was converted from — a CRM fact the app must not learn.
`get_messages(references)` takes a JSON list of `[doctype, docname]` pairs, so the host
decides what a conversation spans, and the endpoint calls `has_permission("read")` on every
pair it is handed. That is **stronger** than a host-registered resolver: a resolver is
trusted to return a safe scope, whereas an argument is assumed hostile and checked.

This is `FP2` correctly read. `PHILOSOPHY.md` scopes FP2 to **list-view controls** — SortBy,
Filter, ColumnSettings, QuickFilter — where the host owns fetching because it owns the
query. An earlier revision of this work read it as "nothing in this library may ever fetch"
and built the package props-in on that basis. That was a misreading: the two modules nearest
to ours do the opposite, `useNotifications` calling `createListResource` and
`useActivityTimeline` calling `createResource`. A composable owning its fetching is house
style. What FP2 does still say is that a *component* stays controlled — and `MessagePanel`
is: the fetching sits in `useMessages()` next to it, not inside it.

## Considered Options

- **Leave the endpoints in CRM and have `@whatsapp/ui` call `crm.api.whatsapp.*`.**
  Rejected: a shared package cannot name one host's app in its URLs. Every other host would
  either install CRM or reimplement the enrichment, and the contract would be hostage to a
  codebase we do not own.
- **Generic endpoints, host-specific data via `frappe.get_hooks` callbacks.** Rejected as
  above: the one host-specific value is per-conversation, not per-message, and is
  presentation. A hook would have made every host's resolver a server-side dependency of a
  read that does not need one.
- **Let the host register a reference-scope resolver instead of passing `references`.**
  Rejected: it moves a security decision into configuration. A registered resolver is
  trusted by construction; an argument is checked on arrival.
- **Keep the library props-in and let each host fetch.** Rejected once the FP2 misreading
  was corrected: it made every host rebuild the same fetch, and left the package's most
  valuable part — knowing how to talk to this app — unshipped.

## Consequences

- The app has a **public API surface** it did not have before: changing one of these
  signatures is a breaking change, with the same care a DocType field rename needs.
- **CRM's five message endpoints are superseded (PR-2)**, and the generic helpers move with
  them. CRM keeps its role gate, `notify_agent`, its doc hooks, and one small function
  computing the Deal→Lead reference list it now passes as an argument.
- **The app's permission check is orthogonal to a host's role policy, not a superset of
  it.** The endpoints guard on the reference document; the app has no role model of its own
  yet (open gap [#10](https://github.com/ps173/frappe-whatsapp/issues/10) — everything else
  requires System Manager). A host that gates WhatsApp by role keeps that gate in front.
- **`references[0]` is where a send attaches.** Extra references only widen the read, so
  scope and destination stay separable without a second argument.
- **Realtime moves to the app.** `publish_realtime("whatsapp_message", …)` fires from
  `WhatsApp Message.on_update`, so any host gets it; `useMessages()` subscribes through the
  host's socket and reloads when the event names one of its references.
- **`@whatsapp/ui` fetches.** `useMessages()` and `useTemplates()` own their resources and
  the host binds a controller instead of writing an API — see
  [`src/components/Messages/README.md`](../../src/components/Messages/README.md).
