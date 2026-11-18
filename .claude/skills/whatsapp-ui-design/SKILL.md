---
name: whatsapp-ui-design
description: UI and UX patterns for screens in `@whatsapp/ui` (and the hosts that embed it). Use when building or reviewing any component in `ui/src`, such as an editor, a list, a header, a status, an error or a preview, so that new screens match the ones already reviewed.
---

# WhatsApp UI design patterns

These patterns come from review rounds on the template editor and the Flow builder. Each pattern is a rule, then the reason. Product decisions about Flows themselves are in `DESIGN_DECISIONS.md`, not here.

## Start from the reference

- **When Meta (or another platform) already has an editor for the thing, recreate its structure first.** The Flow builder copies Meta's Flows playground: a Screens list, an "Edit content" accordion, and a phone preview. Change it only where our product needs more (saving, status, publishing).
  Why: users know the platform's editor, and the first design invented from scratch was rejected.
- **Style it the Espresso way through frappe-ui.** frappe-ui 1.0 uses the Espresso v2 tokens, so no new colours are needed.

## Components

- **Use frappe-ui components for everything**, and don't override their size or shape. Examples: `Button`, `Dropdown`, `Badge`, `Alert`, `Switch`, `TextInput`, `Tooltip`, `toast`, `dialog.confirm`. A hand-made `<button>` is acceptable only in two cases:
  - a whole clickable row;
  - content that mimics another app, such as the WhatsApp phone preview.

  Why: a fixed width on a frappe-ui `Button` made "Publish" look broken.
- **Check what the component can already do before building around it.** For example, `Alert` draws one row when it has only a title and a primary action. Use its slots (`#title`) for inline links rather than a second line.

## Hierarchy and noise

- **Show a state only when it is not the default.** A Draft Flow has no "Draft" badge. A saved Flow shows no "Saved" text. Show only "Saving…" while a save runs and "Couldn't save · Retry" after a failure.
  Why: a default state next to its saving state reads as noise.
- **Use one primary action.** If an action can happen by itself, don't give it a button: saving is automatic, so Publish is the only button.
- **Give one way out.** The breadcrumb (and Escape) closes the builder; there is no ✕ next to it.
- **Use neutral gray for selected and hover.** Colour only encodes status or severity: red for Blocked and errors, amber for Throttled and warnings.
- **A banner's colour follows its severity**, and the banner links to where the user can act. Example: "See why in WhatsApp Manager ↗".

## Layout and alignment

- **Reserve a lane only for something that can appear in it.** Rows that can never be dragged (Screen title, Button, read-only lists) have no empty grip lane, so their text lines up with the content under them. Lanes that change content in place, such as a warning icon, stay reserved on every row.
- **Banners must not take space from the main work area.** Keep them to one row.
- **Keep the structure fixed.** A non-movable first row and last row (Screen title, Button) frame the movable rows. New items go just before the fixed last row, already open.

## Layout shift and motion

- **Aim for near-zero layout shift.**
  - Give status text a fixed-width slot.
  - Put character counters (`n/max`) inside the input.
  - Make toggles keep the box size; hide with `invisible`, not `v-if`, when the space must stay.
  - A preview frame keeps its size across modes and themes.
- **Make transitions short and quiet:** about 150 ms fades. Accordions use 200 ms on `cubic-bezier(.23,1,.32,1)`. Respect `motion-reduce`.
- **Measure the boxes before and after** each state change (select, type, save, error) when you check a change. The one accepted shift is an error line under a field, which pushes the rows below it.

## Errors and limits

- **Show errors on the thing that is wrong:** the field gets the error state, and its row and screen get a warning icon. A count in the header jumps to the first problem.
- **Stop input at the limit, and show the limit.** Use the counter inside the input and `maxlength`. A control disabled by a limit has a tooltip that says why.
- **Treat the server's validation result as data, not a failure.** Place each error on its row.
- **Don't ask before a deletion you can undo.** Delete at once and offer Undo in a toast. Confirm only what can't be undone, such as Publish.

## Saving

- **Save automatically**, debounced (about 1.5 s after the last edit), one save at a time.
- **Flush pending saves before any action that depends on them:** Publish, close, copy, apply.
- **Close without asking**, unless the last save failed.
- **A conflict (the record changed elsewhere) stops saving** and shows a reload Alert.

## Strings

- **Every visible string goes in the component's Chrome object** (for example `FLOW_BUILDER_CHROME`) with English defaults, so hosts pass translated strings.
- **Use sentence case, short words, and the user's words.** Write "Hide in chat", not "sensitive".

## How work is reviewed

- **The first cut is for feedback.** Focus on information hierarchy, error handling and simple UX, not polish.
- **Show every reachable state in Storybook** (`ui-dev/`, git-excluded) through a State switch, one switch per independent thing. Take screenshots next to the reference.
