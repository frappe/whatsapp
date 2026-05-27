# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Frappe app providing WhatsApp Business Cloud API (Graph API v22.0) integration. Built on the Frappe framework — all DocType, ORM, lifecycle, and testing patterns come from Frappe conventions.

**Canonical reference:** `~/Dev/frappe-bench/apps/frappe/` — always check Frappe source for framework APIs before assuming behavior.

## Commands

```bash
# Run all tests
bench run-tests --app whatsapp

# Run tests for a single doctype
bench run-tests --app whatsapp --doctype "Whatsapp Message"

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
    whatsapp.py                 # Whatsapp class — wraps all Facebook Graph API calls
    utils.py                    # Template payload builders, {{var}} interpolation, log() utility
  doctype/
    whatsapp_account/           # Per-account config (phone_number_id, token, auto_read_receipts)
    whatsapp_account_append/    # Child table: Append Actions config per account
    whatsapp_message/           # Core message record (inbound + outbound)
    whatsapp_template/          # Template management + Meta sync (hourly scheduled job)
    whatsapp_template_button/   # Child table for template buttons
    whatsapp_message_interactive_button/  # Child table for interactive message buttons
    whatsapp_message_list_item/ # Child table for list message items
    whatsapp_profile/           # Auto-created contact record for each unique sender
    whatsapp_log/               # Audit log for all webhook/API/template/message events
    whatsapp_setting/           # App-level singleton settings
    template_variable/          # Child table for named/positional template variables
  notification/                 # 6 built-in Frappe Notifications (received, sent, failed, etc.)
```

**Message flow (inbound):** Meta → `webhook.py` → creates `Whatsapp Message` + `Whatsapp Profile` → triggers Append Actions → fires Frappe Notifications.

**Message flow (outbound):** Caller creates `Whatsapp Message` doc → `whatsapp_message.py` `after_insert` → `Whatsapp` API class → logs result in `Whatsapp Log`.

**Template sync:** `whatsapp_template.sync_all` runs hourly via scheduler hooks. Sample templates are flagged and skipped to avoid unnecessary Meta API calls.

## Key Conventions

**Logging:** All significant events MUST use `log()` from `whatsapp.whatsapp.api.utils` — this creates browsable `Whatsapp Log` records. `frappe.logger()` writes to files only and is not sufficient.

```python
from whatsapp.whatsapp.api.utils import log

log(
    level="Info",          # Info | Warning | Error | Debug
    event_type="Message",  # Webhook | Template | Message | API | System
    message="...",
    account="...",         # optional Whatsapp Account name
    reference_doctype="Whatsapp Message",
    reference_docname=doc.name,
    request_data={...},    # outgoing payload
    response_data={...},   # API response
)
```

**Type annotations:** Required on all whitelisted API methods (`require_type_annotated_api_methods = True` in hooks).

**Template variables:** Use `{{variable_name}}` syntax in message/header text.

**Auto-generated type blocks:** DocType classes contain `# begin: auto-generated types` blocks — never edit manually.

**Indentation:** Tabs (ruff config), double quotes, line length 110.

## Commit Style

Conventional Commits required. Format: `type(scope): description`

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`. Breaking changes: append `!` before `:` or include `BREAKING CHANGE:` footer.

Examples:
```
feat(message): add reply-to support for outbound messages
fix(webhook): handle missing account gracefully
feat!: rename WhatsappSetting fields
```

## Testing Patterns

Tests extend `frappe.tests.IntegrationTestCase` (auto-rollback, test records) or `UnitTestCase` (no DB). Test files live inside the doctype folder alongside the controller.

```python
from frappe.tests import IntegrationTestCase

class TestWhatsappMessage(IntegrationTestCase):
    def test_something(self):
        doc = frappe.get_doc({"doctype": "Whatsapp Message", ...}).insert()
        self.assertEqual(doc.status, "Sent")
```

Fixture records go in `test_records.json` in the doctype folder.
