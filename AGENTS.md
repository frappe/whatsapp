# WhatsApp - Frappe App

## What this is

Official WhatsApp integration for Frappe CRM. A Frappe app that provides DocTypes and utilities for interacting with the WhatsApp Business Cloud API (Graph API v22.0).

## Repo structure

- `whatsapp/` — Frappe app package
  - `whatsapp/doctype/` — DocTypes: `WhatsAppSettings`, `WhatsAppAccount`, `WhatsAppMessage`, `WhatsAppTemplate`, `WhatsAppLog`, `TemplateVariable`, `WhatsAppTemplateButton`, `WhatsAppAccountAppend`
  - `whatsapp/api/whatsapp.py` — `WhatsApp` class wrapping Facebook Graph API calls
  - `whatsapp/api/utils.py` — Template payload builders/parsers, `{{var}}` interpolation helpers, `log()` utility, `get_logs()` whitelisted API
  - `hooks.py` — Frappe hooks (most commented out; early stage)
  - `modules.txt` — Single module: `WhatsApp`

## Validation

- Run `python3 -m py_compile <file>.py` to check syntax without needing bench's virtualenv.
- Run `bench console` then `import <module>` to check imports resolve correctly within the bench environment.
- To run Ruff within the bench environment: `bench setup requirements --dev` then `python3 -m ruff check <file>.py`.

## Tooling config

| Tool             | Config                         | Notes                                                                                        |
| ---------------- | ------------------------------ | -------------------------------------------------------------------------------------------- |
| **Python**       | `>=3.14`                       | Pinned in pyproject.toml                                                                     |
| **Build**        | `flit_core`                    | Managed by bench, not pip                                                                    |
| **Ruff**         | `pyproject.toml`               | line-length=110, tab indent, double quotes                                                   |
| **Ruff ignores** | See pyproject.toml lines 40-58 | Notably: F401 (unused imports), E501 (line length), UP030/UP032 (f-strings for translations) |
| **basedpyright** | `typeCheckingMode = "off"`     | Type annotations exported but not checked                                                    |
| **ESLint**       | `.eslintrc`                    | Most rules off; `frappe` global available                                                    |
| **Prettier**     | `.pre-commit-config.yaml`      | JS/Vue/SCSS only; excludes dist/, lib/, templates/                                           |

## Conventions

- **Indent style**: Tabs for Python (ruff format config), consistent with Frappe defaults
- **Template variables**: Use `{{variable_name}}` syntax in message/header text
- **Type annotations**: Required on all whitelisted API methods (`require_type_annotated_api_methods = True`)
- **Auto-generated types**: DocType classes have `# begin: auto-generated types` blocks — do not edit manually

## Testing

### Running tests

```bash
bench run-tests --app whatsapp               # all tests
bench run-tests --app whatsapp --doctype "WhatsAppTemplate"   # single doctype
bench run-tests --app whatsapp --test test_validation_method   # single test method
bench run-tests --app whatsapp --module "whatsapp.api"        # module outside doctype dir
bench run-tests --app whatsapp --profile                      # with profiling
```

### Test base classes (from `frappe.tests`)

| Class | Purpose |
|---|---|
| **`IntegrationTestCase`** | **Primary class for doctype tests.** Auto-creates test records from `test_records.json`, manages DB (auto-rollback via `addClassCleanup`), provides query/Redis counters. |
| **`UnitTestCase`** | Lightweight, no DB setup beyond site init. For isolated unit tests. |
| **`MockedRequestTestCase`** | Same as `IntegrationTestCase` with `responses.RequestsMock` auto-managed for HTTP mocking. |

### Test file structure

```
whatsapp/doctype/<name>/
  __init__.py
  <name>.py                       # Document controller
  <name>.json                     # DocType definition
  test_<name>.py                  # Test file — class name: IntegrationTest<Name>
  test_records.json               # (optional) Fixture records for integration tests
```

Test files live inside the doctype folder. The doctype is auto-detected from the module path by walking up `cls.__module__.split(".")` until `"doctype"` is found, then reading the adjacent `*.json` for the `"name"` field.

### Test records / fixtures

Test records are resolved in this priority order:
1. `_make_test_records()` generator function in the test module
2. `test_records` list in `.py` (deprecated)
3. **`test_records.json`** in doctype folder (preferred)
4. `test_records.toml` (future)

**Dependency control** — module-level constants in the test file:
```python
EXTRA_TEST_RECORD_DEPENDENCIES = []    # additional doctypes to create records for
IGNORE_TEST_RECORD_DEPENDENCIES = []   # link-field doctypes to skip
```

Dependency resolution is automatic and depth-first — it reads Link fields from DocType meta and recurses via `get_missing_records_doctypes()`.

### Patterns for creating docs in tests

```python
# Dict-based (most common)
doc = frappe.get_doc({"doctype": "ToDo", "description": "test"}).insert()

# Kwargs-based (concise)
doc = frappe.get_doc(doctype="ToDo", description="test").insert()

# new_doc-based
doc = frappe.new_doc("ToDo")
doc.description = "test"
doc.insert()
```

### Assertions

**Standard unittest:**
```python
self.assertTrue(cond); self.assertFalse(cond)
self.assertEqual(a, b)
self.assertIn(item, collection)
self.assertRaises(frappe.ValidationError, doc.save)
```

**Frappe-specific (from `UnitTestCase`):**
```python
self.assertDocumentEqual({"subject": "test", "status": "Open"}, doc)
self.assertQueryEqual(sql_a, sql_b)
self.assertSequenceSubset(larger, smaller)
```

**Query counters (context managers on `IntegrationTestCase`):**
```python
with self.assertQueryCount(5):
    doc.reload()

with self.assertRowsRead(10):
    frappe.get_all("ToDo")
```

### Lifecycle

```python
class TestToDo(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()   # creates test records, inits site

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        frappe.db.delete("ToDo")  # clean slate per test

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()
```

DB auto-rolls back via `addClassCleanup` — no explicit cleanup needed unless targeting a clean slate per test.

### Useful utilities

```python
frappe.set_user("test@example.com")          # switch user
IntegrationTestCase.change_settings("System Settings", {"logout_on_password_reset": 1})  # temp config
self.freeze_time(datetime(...))              # freeze time within test
frappe.db.exists("ToDo", name)               # existence check
frappe.delete_doc_if_exists("ToDo", name)    # safe deletion
frappe.clear_cache(doctype="ToDo")           # clear cached meta
frappe.generate_hash()                       # unique string for test data
frappe.in_test                               # bool check if running in test mode
```

### Writing tests for utility functions (no DB needed)

Use plain classes with plain `assert` — no base class required:
```python
class TestUtils:
    def test_some_function(self):
        result = my_function("input")
        assert result == "expected"
```

### Integration test records (`test_records.json`)

```json
[
    {
        "doctype": "WhatsAppTemplate",
        "template_name": "_Test Template",
        "language": "en_US",
        "template_type": "UTILITY",
        "message": "Hello {{1}}"
    }
]
```

The test runner loads these automatically when the test class extends `IntegrationTestCase`. Place the file in the same doctype directory as `test_<name>.py`.

## Installation (for reference)

```bash
bench get-app <repo-url> --branch main
bench install-app whatsapp
```

## Reference source

**The canonical Frappe framework lives at `~/Dev/frappe-bench/apps/frappe/`. When in doubt about ANY Frappe API, convention, DocType definition, or testing pattern, refer directly to the source code there — it supersedes ALL documentation. Always look there first before asking questions.**

## Logging

All significant events MUST be recorded via the `log()` function from `whatsapp.whatsapp.api.utils`. This creates a browsable `WhatsApp Log` record in the desk UI, unlike `frappe.logger()` which writes to log files only.

### log() signature

```python
log(
    level: str,          # "Info" | "Warning" | "Error" | "Debug"
    event_type: str,     # "Webhook" | "Template" | "Message" | "API" | "System"
    message: str,        # Human-readable summary
    account: str,        # Optional — link to WhatsApp Account
    reference_doctype: str,  # Optional — e.g. "WhatsApp Message"
    reference_docname: str,  # Optional — the document name
    request_data: str|dict, # Optional — request/outgoing payload
    response_data: str|dict, # Optional — response/incoming data
    traceback: str,      # Optional — auto-populated if level="Error"
)
```

### When to log

| Event Point | Level | Event Type |
|---|---|---|
| Webhook received | Info | Webhook |
| Incoming message created | Info | Webhook |
| Message status changed (delivered/read) | Info | Webhook |
| Message status changed (failed) | Warning | Webhook |
| Template approved/rejected via webhook | Info | Webhook |
| Unknown message_id in status update | Warning | Webhook |
| Unknown template_id in status update | Warning | Webhook |
| Missing account for webhook | Error | Webhook |
| HMAC verification failure | Error | Webhook |
| Outgoing message sent | Info | Message |
| Outgoing message send failed | Error | Message |
| Append action failed | Error | Message |
| Template pushed to Meta | Info | Template |
| Template updated in Meta | Info | Template |
| Template push/update failed | Error | Template |
| Sync completed | Info | Template |
| Template marked DELETED | Info | Template |
| Template skipped (SAMPLE) | Debug | Template |
| API request succeeded | Debug | API |
| API request failed | Error | API |

### Log retention

`WhatsApp Log` uses `track_changes = 1` and `naming_rule = "Random"`. There is no built-in cleanup — add a scheduled automation or `frappe.desk.doctype.tag.tag.remove_tags()` if log rotation is needed.

## Key notes

- **Frappe dependency** is installed and managed by bench, not listed in pyproject.toml
- **Patches**: `patches.txt` is empty — no migrations defined yet
- **Hooks**: Almost all hooks in `hooks.py` are commented out — app is in early development
- **`fetch()` webhook** in `whatsapp_template.py` is a TODO stub

## User Notes

- Do not commit directly. Only commit when user asks

## COMMIT SPEC

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL NOT”, “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in RFC 2119.

- Commits MUST be prefixed with a type, which consists of a noun, feat, fix, etc., followed by the OPTIONAL scope, OPTIONAL !, and REQUIRED terminal colon and space.
- The type feat MUST be used when a commit adds a new feature to your application or library.
- The type fix MUST be used when a commit represents a bug fix for your application.
- A scope MAY be provided after a type. A scope MUST consist of a noun describing a section of the codebase surrounded by parenthesis, e.g., fix(parser):
- A description MUST immediately follow the colon and space after the type/scope prefix. The description is a short summary of the code changes, e.g., fix: array parsing issue when multiple spaces were contained in string.
- A longer commit body MAY be provided after the short description, providing additional contextual information about the code changes. The body MUST begin one blank line after the description.
- A commit body is free-form and MAY consist of any number of newline separated paragraphs.
- One or more footers MAY be provided one blank line after the body. Each footer MUST consist of a word token, followed by either a :<space> or <space># separator, followed by a string value (this is inspired by the git trailer convention).
- A footer’s token MUST use - in place of whitespace characters, e.g., Acked-by (this helps differentiate the footer section from a multi-paragraph body). An exception is made for BREAKING CHANGE, which MAY also be used as a token.
- A footer’s value MAY contain spaces and newlines, and parsing MUST terminate when the next valid footer token/separator pair is observed.
- Breaking changes MUST be indicated in the type/scope prefix of a commit, or as an entry in the footer.
- If included as a footer, a breaking change MUST consist of the uppercase text BREAKING CHANGE, followed by a colon, space, and description, e.g., BREAKING CHANGE: environment variables now take precedence over config files.
- If included in the type/scope prefix, breaking changes MUST be indicated by a ! immediately before the :. If ! is used, BREAKING CHANGE: MAY be omitted from the footer section, and the commit description SHALL be used to describe the breaking change.
- Types other than feat and fix MAY be used in your commit messages, e.g., docs: update ref docs.
- The units of information that make up Conventional Commits MUST NOT be treated as case-sensitive by implementors, with the exception of BREAKING CHANGE which MUST be uppercase.
- BREAKING-CHANGE MUST be synonymous with BREAKING CHANGE, when used as a token in a footer.

## Code Practices

Frappe framework conventions observed across the codebase at `frappe/`. Follow these patterns when writing code.

### 1. DocType Python Classes

**Inheritance:** Every DocType controller inherits from `frappe.model.document.Document`.

```python
from frappe.model.document import Document

class MyDocType(Document):
```

**Auto-generated type block:** Every DocType class has an `# begin: auto-generated types` block immediately after the class declaration (before any methods). Each field annotated using `frappe.types.DF.*` aliases. Wrapped in `if TYPE_CHECKING:`. NEVER EDIT MANUALLY.

**Standard lifecycle method ordering** (when present):

1. `__init__` — only override when extra init needed (rare; always `super().__init__()`)
2. `__setup__` — sets flags
3. `autoname` — set document name
4. `onload` — set `self.set_onload(key, value)` for client-side data
5. `before_insert` / `after_insert`
6. `validate` — all validation logic (most common)
7. `before_save`
8. `on_update` — after save complete
9. `on_trash` — before delete
10. `before_rename` / `after_rename`
11. `has_website_permission` — for web-facing doctypes

**Method naming:** `snake_case`. Short verbs. Common prefixes: `validate_*`, `set_*`, `get_*`, `check_*`, `ensure_unique_*`, `sync_*`.

**Class-level constants:** `UPPER_SNAKE_CASE`.

**Docstring style:** One-line `"""triple double quotes"""` imperative ("set name as X", not "Sets name as X").

**Property decorators:** `@property` and `@cached_property` (from `functools`).

**The `@Document.hook` pattern:** Makes methods overridable via hooks.

### 2. API / Whitelisted Methods

**`@frappe.whitelist()`** — always with parentheses. Optional kwargs:

- `allow_guest=True` — exposes to non-logged-in users
- `methods=["GET", "POST"]` — restricts HTTP methods
- `xss_safe=True` — for guest methods

**Whitelisted functions:** Live at module level for REST endpoints. Can be instance methods on Document. Always have full type annotations on parameters.

**Rate limiting:** `@frappe.rate_limiter.rate_limit` stacked after `@frappe.whitelist()`.

**Response patterns:** Return a dict/serializable value. Set HTTP status via `frappe.response.http_status_code`. Use `frappe.respond_as_web_page()` for HTML error pages.

**`frappe.only_for(role)`** — permission guard inside whitelisted functions.

### 3. Utility / Helper Modules

**Function naming:** `snake_case`. Verb-first. Common prefixes: `get_*`, `set_*`, `is_*` / `has_*`, `validate_*`, `_` prefix for private helpers.

**Module organization:** Topic-based modules under `frappe/utils/`. Wildcard re-exports in `__init__.py`.

**Compile-time regex constants:** Module-level `re.compile()` patterns in `UPPER_SNAKE_CASE`.

**Top-level constants:** `UPPER_SNAKE_CASE` at module level.

### 4. Model / ORM Patterns

**Field value access:** Prefer `self.get(fieldname)` / `self.set(fieldname, value)` over direct attribute access.

**Child table handling:**

- `self.append("child_table_field", {dict data})` to add rows
- `self.get("child_table_field")` returns list of child doc dicts
- `self.remove(child_row)` to remove a row

**Standard query patterns:**

- `frappe.get_all(doctype, filters=..., fields=..., pluck="name")` — lightweight list
- `frappe.get_doc(doctype, name)` — full document load
- `frappe.get_cached_doc(doctype, name)` — cache-aware load
- `frappe.db.get_value(doctype, name, fieldname)` — single value
- `frappe.db.get_single_value("DocType", "field")` — single doctype values
- `frappe.db.set_value(doctype, name, field, value)` — direct DB update
- `frappe.db.exists(doctype, filters)` — existence check
- QB (Query Builder): `frappe.qb.DocType("Table")` for type-safe queries

### 5. Import Conventions

Standard ordering (separated by blank lines):

1. Python standard library
2. Third-party libraries
3. Frappe framework imports (`import frappe`, `from frappe import _`, `from frappe.model.document import Document`)
4. Same-app relative imports

**`TYPE_CHECKING` guards:** All imports only used for type annotations go inside `if TYPE_CHECKING:` blocks.

### 6. Error Handling Patterns

**Raising errors:** Prefer `frappe.throw(msg, exc)` or `raise frappe.SpecificError`.

**Common exception classes:**

- `frappe.ValidationError` (HTTP 417) — most common
- `frappe.PermissionError` (HTTP 403)
- `frappe.AuthenticationError` (HTTP 401)
- `frappe.DoesNotExistError` (HTTP 404)
- `frappe.DuplicateEntryError` (HTTP 409)
- `frappe.MandatoryError`, `frappe.LinkValidationError`, `frappe.NameError`

**Exception class patterns:** Inherit from `frappe.ValidationError`, set `http_status_code` as class attr, short docstring or `pass`.

**Logging errors:** `frappe.log_error(title="...", message=frappe.get_traceback())`.

### 7. Configuration and Constants

**Module-level constants:** `UPPER_SNAKE_CASE` after imports, before class.

**Frozen sets** for immutability.

**Sentinel values:** `UNSET = object()` or `_NOT_IN_CACHE = object()`.

**Type aliases:** `TypeAlias` from `typing` for complex types.

### 8. Decorator Usage

- `@frappe.whitelist()` — always with parentheses
- `@staticmethod` / `@classmethod` — sparingly, mostly for factory methods
- `@property` / `@cached_property` — computed properties
- `@http_cache(max_age=...)` — caching API responses
- `@task(queue="short")` — background job
- Chaining order: `@frappe.whitelist()` then `@rate_limit()` then `def my_method():`

### 9. Comment / Docstring Style

**Copyright header:** Every `.py` file starts with:

```python
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
```

**Docstring style:** One-line `"""triple double quotes"""`. Multi-line uses short summary, blank line, then longer description with `:param name:` Sphinx-style parameter docs.

**Inline comments:** `#` with a space. Used for TODOs, architectural notes, deprecation notes, security notes.

### 10. Type Annotation Patterns

- All whitelisted methods must have fully annotated parameters (enforced by `require_type_annotated_api_methods = True`)
- Return type annotations always present on public methods
- Use `| None` syntax (Python 3.10+) for optional values: `name: str | None = None`
- Use `Self` return type for fluent methods
- DF types for DocType fields: `DF.Data`, `DF.Check`, `DF.Int`, `DF.Literal[...]`, `DF.Table[Child]`, etc.
- `TYPE_CHECKING` guard for type-only imports
- `@override` decorator (Python 3.12+) for overriding parent methods

### 11. File Structure for a DocType

Within a doctype folder `<name>/`:

```
name/
  __init__.py           (empty)
  name.py               (controller — Document subclass + whitelisted module-level functions)
  name.json             (DocType definition in JSON)
```

The `name.py` file structure:

1. Copyright header
2. Stdlib imports
3. Third-party imports (blank line)
4. Frappe imports (blank line)
5. Local / same-app imports (blank line)
6. `TYPE_CHECKING` block (blank line before)
7. Module-level constants (blank line before)
8. Exception classes (if any)
9. Document subclass with auto-generated types block
10. Document methods in standard lifecycle order
11. Whitelisted module-level functions
12. Helper module-level functions (private)

### Summary of Naming Conventions

| Concept                 | Convention                            | Example                                   |
| ----------------------- | ------------------------------------- | ----------------------------------------- |
| DocType class           | PascalCase (matches DocType name)     | `class User(Document):`                   |
| Methods/Functions       | `snake_case`                          | `validate_email_type()`                   |
| Module-level constants  | `UPPER_SNAKE_CASE`                    | `STANDARD_USERS`                          |
| Class-level constants   | `UPPER_SNAKE_CASE`                    | `DOCTYPE = "Email Queue"`                 |
| Private helpers         | `_` prefix                            | `_get_timezones()`                        |
| Module-level variables  | `lower_snake_case`                    | `no_cache = True`                         |
| Parameters              | `snake_case`                          | `new_password: str`                       |
| Type aliases            | PascalCase or camelCase               | `DateTimeLikeObject`                      |
| Compiled regex patterns | `UPPER_SNAKE_CASE`                    | `EMAIL_MATCH_PATTERN`                     |
| Exceptions              | PascalCase (`ValidationError` suffix) | `class InvalidNameError(ValidationError)` |
