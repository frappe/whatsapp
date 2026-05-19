# WhatsApp - Frappe App

## What this is

Official WhatsApp integration for Frappe CRM. A Frappe app that provides DocTypes and utilities for interacting with the WhatsApp Business Cloud API (Graph API v22.0).

## Repo structure

- `whatsapp/` — Frappe app package
  - `whatsapp/doctype/` — DocTypes: `WhatsappSetting`, `WhatsappAccount`, `WhatsappMessage`, `WhatsappTemplate`, `TemplateVariable`, `WhatsappTemplateButton`
  - `whatsapp/api/whatsapp.py` — `Whatsapp` class wrapping Facebook Graph API calls
  - `whatsapp/api/utils.py` — Template payload builders/parsers, `{{var}}` interpolation helpers
  - `hooks.py` — Frappe hooks (most commented out; early stage)
  - `modules.txt` — Single module: `Whatsapp`

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

- Tests use `frappe.tests.IntegrationTestCase`
- Test records are auto-generated from DocType JSON definitions
- Run via Frappe bench: `bench run-tests --app whatsapp`

## Installation (for reference)

```bash
bench get-app <repo-url> --branch main
bench install-app whatsapp
```

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
