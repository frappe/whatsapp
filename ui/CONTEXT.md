# WhatsApp Messages (shared `@whatsapp/ui`)

The domain of the reusable WhatsApp conversation UI being extracted from CRM into
`@whatsapp/ui`: a rendered exchange of messages with one contact, and the
**Controller** that fetches it, composes into it and sends. The components render
and emit; the Controller does the reading and the writing, against the WhatsApp
app's own endpoints.

## Language

**Message**:
One `WhatsApp Message` document — the atom of the conversation, inbound or
outbound. Reactions arrive as Messages too, but they are folded away before the
library sees them (see **Reaction**), so a Message in the view model is always
something a **Bubble** is drawn for.
_Avoid_: "chat", "note" (CRM's other feed entries).

**Bubble**:
The rendered form of one Message — the whole of it, including the chrome drawn
outside its coloured body. The Bubble is presentation and the Message is data;
"which side is it on", "does it show a tick", "is the media inline" are all
Bubble questions, even though the tick is not inside the coloured body.
_Avoid_: "activity" (CRM's name for a row in its mixed Deal/Lead feed, where
WhatsApp messages sit alongside calls, notes and tasks — that feed is a host
concern and its vocabulary does not travel with the extracted package); using
"bubble" for the coloured body alone (there is one word here for the whole
rendered Message, and no separate name for the body).

**Participant**:
One of the two sides of a conversation: the **agent** (the app's user, labelled
"You") and the **contact** (the person on WhatsApp). Every Message, and every
**Reaction**, belongs to exactly one Participant.
_Avoid_: "user" (ambiguous — the contact is also a person), "sender" for the
Participant itself (**Sender name** is the string that labels one, not a synonym).

**Sender name**:
The display name shown for a Participant — the **Host**-supplied string naming the
contact, and the "You" label for the agent. It is a **prop**, not a field: for a
given conversation it is one string, the same on every **Bubble** of that
**Direction**, and choosing between the two by Direction is presentation. So it
never travels on the wire and no Message carries it.
_Avoid_: "from name" (`from_name` was the server-computed field this replaced —
see "Design decisions" in [README.md](README.md)), "reactor name"
(same string, reached the same way; a **Reaction** carries only its Direction).

**Direction**:
Which Participant a Message came from: `Incoming` (the contact) or `Outgoing`
(the agent). Title Case, as stored. Direction is the only axis the UI needs to
place a Bubble on a side; there is no separate "is this mine" concept.
_Avoid_: **"type"** — CRM's legacy name for this field, and now genuinely
misleading, because "type" reads as the *kind* of thing a message is (see
**Render kind**, **Template**) rather than which way it travelled.

**Status**:
A Message's delivery lifecycle: `Pending` → `Sent` → `Delivered` → `Read`, or
`Failed`. Title Case, exactly as stored. `Pending` is the initial state — every
message starts there and stays there until the send call returns, and it
deliberately shows no delivery mark at all.
_Avoid_: lowercased status values (CRM normalizes case at its API boundary; that
is the legacy behaviour this package exists to stop — see
"Design decisions" in [README.md](README.md)), "state", "read
receipt" (that names one Status, not the axis).

**Render kind**:
How a Message's body should be drawn: `text`, `image`, `audio`, `video` or
`document`. Always **derived** from the Message's MIME type, never stored and
never overridable — no MIME type means `text`, and anything that is not image,
audio or video is a `document`.
_Avoid_: treating it as a **field**. CRM's `content_type` was a computed value the
server injected into the payload, not a column; nothing sends one now. Also avoid
"media type" (that is the MIME type it is derived *from*).

**Reaction**:
One emoji a **Participant** attached to a Message. Each Participant keeps at most
one Reaction per Message — reacting again *replaces* that Participant's previous
one — so a Message carries zero to two Reactions, at most one per side. WhatsApp
delivers Reactions as Messages of their own pointing back at a target; the app's
`get_messages` folds those onto their target before the UI sees them.
_Avoid_: "like", "emoji" alone (the emoji is one attribute of a Reaction, and
emoji also appear in message bodies), "reaction count" (there is no tally).

**Quote** (or **reply context**):
The block above a Bubble showing the Message this one replies to. A Quote is a
pointer plus enough of the referenced Message to render a preview and to scroll
to the original.
_Avoid_: **"thread"** — a Quote does not group Messages. The conversation stays a
single flat sequence in send order; nothing nests, collapses, or gets counted as
belonging to a reply.

**Day separator**:
The labelled rule drawn between the last Message of one calendar day and the
first of the next. It is the only structure the conversation imposes on its
Messages — they otherwise run as one flat sequence in send order, with no
grouping of consecutive Messages by Participant or by time.
_Avoid_: "date header" (it separates, it does not head a section), "divider"
(the underlying frappe-ui primitive is called that; the Day separator is the
thing made of one).

**Template**:
A pre-approved `WhatsApp Template` document, referenced by docname. This is
*provenance*: "this Message was sent from a Template, and here is which one."
_Avoid_: using "template" bare when you mean the text (see below).

**Rendered template body**:
The Template's text with its variables already substituted — the actual words the
contact received. Only the server can produce it, because substitution reads the
referenced document. A Bubble displays the Rendered template body; it never sees
raw `{{variables}}`.
_Avoid_: collapsing this into **Template**. CRM's API returns both under the same
key, overwriting the docname with the rendered text partway through the response
— live evidence that one word for two things is a trap. Name them separately.

**Controller**:
A composable that owns a slice of data plus the verbs that change it, which a
**Host** binds onto a component (`useMessages`, `useTemplates`). A Controller
fetches, writes, and holds what is being composed; the component it feeds only
renders and emits. Data spreads in with `v-bind`; actions come back as events
wired to the Controller's verbs.
_Avoid_: **"adapter"** — the retired term for a *host-side* function that shaped a
host's API response into the view model. There is no such function now: the app's
own endpoints return the view model, so there is nothing to shape (see
"Design decisions" in [README.md](README.md)). Also avoid "store"
(a Controller is per-conversation, not a singleton) and "hook" (a Frappe hook is
a different mechanism, and one this package deliberately does not use).

**Host**:
The consuming app that owns the surrounding UI — CRM, Helpdesk, or any Frappe app
that mounts these components. The Host decides *what a conversation is* (the
reference documents it spans), *who* it is with (the recipient and the **Sender
name**), and where the UI sits in its layout. It no longer fetches or persists
Messages; a **Controller** does. Anything requiring knowledge of the Host's own
DocTypes or roles is by definition a Host concern.
_Avoid_: "parent app", "consumer" (fine in prose, but "Host" is the term the docs
use).

**Part**:
An individually exported piece of the UI — the message list, a bubble, the input,
a template's rendered body, the reaction bar. Parts are all there is: there is no
composite that assembles them, because assembly is where a **Host**'s layout lives.
Every Part is public and mounted directly.
_Avoid_: "sub-component", "internal" (a Part is public), and **"composite"** /
"panel" — `MessagePanel` was such a component and was removed. It wrapped the list
in loading and empty states and forwarded props, which is not a layer worth the
indirection, and it owned a dialog from inside a scroll region.

A Part draws content, never its container. `MessageBubble` draws one Message and
`TemplateContent` one **Template**; a dialog, a grid or a picker around either is
Host layout. `TemplateSelectorDialog` broke that rule — it shipped a Dialog, a
search box and a grid to deliver one renderer — and was removed for it.

**Chrome**:
User-facing English strings the library renders — placeholders, button labels,
empty states. Every one is exposed with an English default so a Host can pass its
own translation in. The library has no i18n of its own; Chrome is the seam that
replaces it.
_Avoid_: "label" alone (too narrow), "copy", "i18n string".

## Example dialogue

— "The bubble shows the wrong text for a template message — it renders the
docname, `WHATSAPP-TEMPLATE-0007`."
— "Then something put the **Template** where the **Rendered template body**
belongs. They are two different values, and they have two different keys for
exactly that reason; CRM's own API returns both under one key, which is how this
bug gets made."

— "Where do I write the mapping from our API rows to `WhatsAppMessage`?"
— "You don't. There is no adapter any more — the app's `get_messages` returns the
view model, and the **Controller** calls it. What you supply is the scope, the
recipient, and the **Sender name**."

— "Should I send a `content_type` alongside `mime_type` so the bubble knows it's
an image?"
— "No — **Render kind** is derived, never stored. Send the MIME type and nothing
else; there is nothing to override."

— "The contact reacted 👍 and then 😂. Do I get two **Reaction**s?"
— "One. Each **Participant** keeps at most one per Message, so the second
replaces the first. You'd only see two if the agent reacted as well — one per
side."

— "Can I collapse a **Quote** and its replies into a thread view?"
— "There is no thread here. A Quote is a pointer to one earlier Message so we can
preview it and scroll to it; the conversation stays flat. Grouping is a **Host**
feature if you want one."

## Design decisions

Only the rules a later change would otherwise undo without noticing, and why. How
things are built is in the code; what is deliberately absent is in
[README.md](README.md#not-included).

**frappe-ui is the only vocabulary.** Espresso (the design system) and frappe-ui
(its Vue implementation) share one token set — identical gray ramp, `420` body
weight, 14px `text-base`. Reference Espresso for *structure*; write frappe-ui
class names. Three traps when porting from it: its `rounded-lg` is 10px and
frappe-ui's is 12px; its `leading-lg` prose line-height is frappe-ui's separate
`text-p-*` scale; and it is on Tailwind v4 while Hosts are on v3, so
`*:data-[slot=x]:`, `wrap-break-word` and `field-sizing-content` all need the v3
spelling.

**Not every utility registers every scale**, and a class for an unregistered pair
fails *silently*. Per `frappe-ui/tailwind/plugin.js`: `text-`/`stroke-`/
`placeholder-` take `ink`; `bg-` takes `surface`; `border-`/`ring-`/`divide-` take
`outline`; `fill-` takes `ink` or `surface`. Two live bugs came from this —
`ring-surface-base` fell back to Tailwind's default *blue* ring, and
`bg-outline-gray-1` produced no colour at all, leaving the **Day separator**'s
rules invisible.

**Both Directions stay light**, incoming `surface-gray-1` and outgoing
`surface-gray-2`. Two darker treatments were built and reverted: Espresso's
inverted sent Bubble dominated the column and read as an error state, and it
forced an on-dark variant onto seven nested surfaces plus a dual-ground
`TemplateContent`; `surface-gray-3` then sank a Template's button rules and the
**Quote** into the Bubble, needing the same per-surface variants for a far
smaller gain. At `gray-2` one nested value reads on both, so direction styles the
Bubble and nothing inside it. Direction was always carried mainly by row
alignment — the shade is a second, quieter cue.

**A Quote is a rule beside two lines, not a card.** In both places one is drawn — inside a
Bubble, and in the composer above the field — it is a `border-l-2` and two stacked lines,
with no fill of its own. The Bubble's quote takes a fill on hover only, because it is a
button that scrolls to the original and losing the resting fill also lost that affordance;
that fill is one shade for both **Direction**s, per the rule above. The composer's is inside
the box's border rather than floating above it, so the box is a single control and a Host's
gutter has one thing to inset.

**A Bubble's footer sits outside its coloured body.** That is what makes the blue
`Read` mark legible: inside, it was 1.06:1 against the body. It also removes the
padding that was reserving room for an overlaid timestamp, and gives a failure
reason somewhere to be read rather than hovered. It costs ~20px per Message.

**Contrast is measured, not eyeballed.** `ink-gray-5` lands at 3.8–4.2:1 on the
light surfaces used here and fails AA for text — `ink-gray-6` is the floor for
secondary text. The reds are a fill ramp at the low end: `ink-red-4` is 1.5:1,
`ink-red-7` is the first that passes.

**The message scroller is a Host concern.** Autoscroll, scroll anchoring and
jump-to-latest belong to whatever feed a Host embeds the conversation in, not to
WhatsApp. Espresso's implementation is worth reading first: a hidden trailing
spacer sized `targetScrollTop + clientHeight − contentHeight` is what lets the
last turn park at the top while a reply streams in below it, and its four scroll
modes are `following-bottom`, `free-scrolling`, `anchored-to-message` and
`settling-jump`.
