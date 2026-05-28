# Design Decisions

This document records intentional product/design decisions for the Whatsapp app. These are choices that constrain how the app works on purpose — they are not bugs or gaps.

## Templates

### Named variables only (no positional)

Whatsapp Templates created via the Desk UI or through this app always use **named variables** (`{{variable_name}}`). The option to switch to **positional variables** (`{{1}}`, `{{2}}`, …) is not exposed to users.

**Rationale:**
- Named variables are self-documenting — `{{customer_name}}` reads clearly, `{{1}}` does not.
- Avoids off-by-one and ordering bugs when templates are edited.
- Single, consistent authoring experience across the app — users never need to learn or choose between two variable styles.

Meta's Cloud API still supports positional variables; this is purely an app-level UX constraint on **authoring**.

**Sync exception:** positional variables are still supported on the **read path** when syncing templates from Meta. Templates that were originally authored on Meta (or in another tool) using `{{1}}`, `{{2}}`, … sync into this app intact and can be sent normally. Users just cannot create or convert *to* positional templates from within the app.

### Reference DocType drives all parameters

A Whatsapp Template stores a **reference DocType**, and all variable values are resolved from a single document of that DocType at send time.

**Rationale:**
- Sending a templated message requires only the reference document — callers do not pass a separate parameters dict.
- One source of truth: the template definition declares both the variable names *and* where their values come from.
- Append Actions, Server Scripts, and ad-hoc sends all share the same resolution path, so behavior is predictable.

Consequence: a template cannot mix values from multiple unrelated DocTypes. If you need data from a related record, expose it through a field (or a virtual/fetched field) on the reference DocType.
