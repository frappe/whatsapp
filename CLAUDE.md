# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Frappe app providing WhatsApp Business Cloud API (Graph API v22.0) integration. Built on the Frappe framework — all DocType, ORM, lifecycle, and testing patterns come from Frappe conventions.

**Canonical reference:** `~/Dev/frappe-bench/apps/frappe/` — always check Frappe source for framework APIs before assuming behavior.

**Related docs:** `AGENTS.md` has exhaustive Frappe coding conventions (naming, lifecycle method ordering, error handling, test fixture patterns) — check it for anything not covered below. `DESIGN_DECISIONS.md` documents intentional product constraints (e.g. named-only template variables, reference-DocType-driven template parameters) that are not bugs.

## Commands

```bash
# Run all tests
bench run-tests --app whatsapp

# Run tests for a single doctype
bench run-tests --app whatsapp --doctype "WhatsApp Message"

# Run a single test method
bench run-tests --app whatsapp --test test_method_name

# Run tests for a module outside doctype dir
bench run-tests --app whatsapp --module "whatsapp.whatsapp.webhook"

# Check syntax without bench virtualenv
python3 -m py_compile whatsapp/whatsapp/api/whatsapp.py

# Lint
python3 -m ruff check whatsapp/

# Format check
python3 -m ruff format --check whatsapp/
```

Pre-commit enforces ruff, eslint, prettier, and pyupgrade — run `pre-commit install` once after cloning.

## Architecture

```
whatsapp/whatsapp/
  webhook.py                    # Meta webhook entry point — validates HMAC, routes to handlers
  api/
    whatsapp.py                 # WhatsApp class — wraps all Facebook Graph API calls
    utils.py                    # Template payload builders, {{var}} interpolation, log() utility
  doctype/
    whatsapp_account/           # Per-account config (phone_id, access_token, auto_read_receipts)
    whatsapp_account_append/    # Child table: Append Actions config per account
    whatsapp_message/           # Core message record (inbound + outbound)
    whatsapp_template/          # Template management + Meta sync (daily scheduled job)
    whatsapp_template_button/   # Child table for template buttons
    whatsapp_message_interactive_button/  # Child table for interactive message buttons
    whatsapp_message_list_item/ # Child table for list message items
    whatsapp_profile/           # Auto-created contact record for each unique sender
    whatsapp_log/               # Audit log for all webhook/API/template/message events
    whatsapp_settings/          # App-level singleton settings
    template_variable/          # Child table for named/positional template variables
  notification/                 # 6 built-in Frappe Notifications (received, sent, failed, etc.)
```

**Message flow (inbound):** Meta → `webhook.py` → creates `WhatsApp Message` + `WhatsApp Profile` → triggers Append Actions → fires Frappe Notifications.

**Message flow (outbound):** Caller creates `WhatsApp Message` doc → `whatsapp_message.py` `after_insert` → `WhatsApp` API class → logs result in `WhatsApp Log`.

**Template sync:** `whatsapp_template.sync_all` runs daily via scheduler hooks (`whatsapp/hooks.py` `scheduler_events`). Sample templates are flagged and skipped to avoid unnecessary Meta API calls.

## Key Conventions

**Logging:** All significant events MUST use `log()` from `whatsapp.whatsapp.api.utils` — this creates browsable `WhatsApp Log` records. `frappe.logger()` writes to files only and is not sufficient.

```python
from whatsapp.whatsapp.api.utils import log

log(
    level="Info",          # Info | Warning | Error | Debug
    event_type="Message",  # Webhook | Template | Message | API | System
    message="...",
    account="...",         # optional WhatsApp Account name
    reference_doctype="WhatsApp Message",
    reference_docname=doc.name,
    request_data={...},    # outgoing payload
    response_data={...},   # API response
)
```

**Type annotations:** Required on all whitelisted API methods (`require_type_annotated_api_methods = True` in hooks).

**Template variables:** Use `{{variable_name}}` syntax in message/header text.

**Auto-generated type blocks:** DocType classes contain `# begin: auto-generated types` blocks — never edit manually.

**Indentation:** Tabs (ruff config), double quotes, line length 110.

## Comments — hard rule

**Code must be self-explanatory. Do not write a comment the code already says.**

If a comment restates the line below it, the fix is a better name, not a comment. Reach for a
clearer function or variable name, or extract a named helper, before reaching for prose.

Delete on sight:

```python
# Get the default account          <- says nothing the name doesn't
account = get_default_account()

# Loop through messages            <- describes the syntax
for message in messages:

def send_message(to, message):
    """Send a message to a recipient."""   # <- restates the signature
```

A comment earns its place only when it carries something the code cannot:

- **Why**, when the reason is not visible — a workaround, a deliberate ordering, an
  upstream quirk. `# anchored to line starts so digits mid-sentence aren't matched as list items`
- **A non-obvious constraint** a future edit would otherwise break — a field that must be
  set before another, a guard that looks removable and isn't.
- **A reference** that saves a hunt — an issue number, a Meta API behaviour, a linked commit.

Docstrings follow the same rule: write one when a function's contract is not obvious from its
name and signature, and say what is *not* obvious — edge cases, what it throws, what shape it
returns. Skip it otherwise. Never restate the parameters.

When editing existing code, delete redundant comments you pass through rather than preserving
them out of politeness.

## Commit Style

Conventional Commits required. Format: `type(scope): description`

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`. Breaking changes: append `!` before `:` or include `BREAKING CHANGE:` footer.

Examples:
```
feat(message): add reply-to support for outbound messages
fix(webhook): handle missing account gracefully
feat!: rename WhatsAppSettings fields
```

## Testing Patterns

Tests extend `frappe.tests.IntegrationTestCase` (auto-rollback, test records) or `UnitTestCase` (no DB). Test files live inside the doctype folder alongside the controller.

```python
from frappe.tests import IntegrationTestCase

class TestWhatsAppMessage(IntegrationTestCase):
    def test_something(self):
        doc = frappe.get_doc({"doctype": "WhatsApp Message", ...}).insert()
        self.assertEqual(doc.status, "Sent")
```

Fixture records go in `test_records.json` in the doctype folder.
