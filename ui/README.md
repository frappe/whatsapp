# @whatsapp/ui

Shared WhatsApp message components for Frappe apps.

The package ships **raw `.vue`/`.ts` source** — there is no build step and no published
bundle. The host app's bundler compiles it in place, so the host owns the toolchain,
the Tailwind scan, and the typecheck.

It ships components *and* the composables that feed them. `useMessages()` and
`useTemplates()` call the WhatsApp app's own whitelisted endpoints, so a host mounts the UI
and binds a controller — it does not write an API or a mapping layer. See
[`src/components/Messages/README.md`](src/components/Messages/README.md) for the full walkthrough.

## Installation into a host app

1. Link the package from the host's `frontend/package.json`:

   ```json
   "dependencies": {
     "@whatsapp/ui": "link:../../whatsapp/ui"
   }
   ```

2. Alias it in the host's `vite.config.js` and dedupe the shared singletons:

   ```js
   resolve: {
     alias: {
       // point at the package's src dir, not src/index.ts, so subpath imports
       // like `@whatsapp/ui/components/Messages` resolve to a real file
       '@whatsapp/ui': path.resolve(__dirname, '../../whatsapp/ui/src'),
     },
     dedupe: ['vue', 'frappe-ui', 'reka-ui', 'dompurify'],
   }
   ```

   Instead of hand-writing the `dedupe` array you can add the plugin, which sets the
   same list via `config()`:

   ```js
   import whatsappUI from '@whatsapp/ui/vite'
   // ...
   plugins: [whatsappUI()]
   ```

See `apps/crm-eventfix/frontend/vite.config.js` for the same setup applied to
`@framework/ui`.

## Host build requirements for icons

Icons come from frappe-ui's lucide integration, in both of its forms — so a host has to
enable **both**, or icons go missing.

1. **The vite plugin**, for the `~icons/lucide/*` imports (`TemplateButtons` picks its icon
   from `button_type` at runtime, which a class name cannot express):

   ```js
   frappeui({ lucideIcons: true })
   ```

2. **A Tailwind `content` glob covering this package**, for the `lucide-*` utility classes
   used everywhere else. Tailwind only generates CSS for classes it finds as complete strings
   in the files it scans, and it does not scan a linked package by default:

   ```js
   // tailwind.config.js
   content: [
     './src/**/*.{vue,js,ts,jsx,tsx}',
     '../../whatsapp/ui/src/**/*.{vue,js,ts,jsx,tsx}',   // ← this package
   ]
   ```

   **Miss this one and nothing errors** — every class-form icon simply renders as empty
   space. `crm-eventfix` already carries the equivalent line for `@framework/ui`.

## Do not install `frappe-ui` or `vue` here

`frappe-ui` and `vue` are **peer dependencies** and must never end up in this package's
`node_modules`. A second copy of either means two module instances at runtime: Vue's
`provide`/`inject` keys stop matching across the boundary (reka-ui, which frappe-ui builds
on, relies on injected context throughout), and two Vue runtimes break reactivity between
host and library components. The host supplies the single copy; the `dedupe` list above is
what keeps it single.

`dompurify` is the only real dependency.

## Conventions

- `.vue` files are **tab-indented, width 4**, per the repo `.editorconfig`. Prettier runs
  in pre-commit and reads that config, so write tabs.
- `.ts` files are **2-space** — the editorconfig glob does not cover `*.ts`, so prettier's
  default applies.
- No build step and no `tsconfig.json`. The consuming host typechecks this source.

## Requires the WhatsApp app on the site

The composables call `whatsapp.whatsapp.api.messages.*` and the `WhatsApp Template` methods
directly, so the site this runs against must have the `whatsapp` app installed. The components
themselves are pure UI and render whatever they are handed, but the batteries-included path
assumes the endpoints are there.

Those endpoints guard on the reference document's read permission. The app has no role model
of its own yet, so a host with its own WhatsApp role policy must keep that gate in front —
see the security note in the [Messages README](src/components/Messages/README.md#security).

## Design decisions

Three choices that look odd without their reasoning.

**The view model uses the DocType's own fieldnames.** CRM's old endpoint returned a dialect
of its own — `direction` as `type`, `media_url` as `attach`, `whatsapp_template` as
`template`, `status` lowercased — built by popping the real fieldnames off each row. The
renames were undocumented and lossy: `mime_type` never reached the client, and `template`
held a docname in one place and rendered prose in another. This package takes the WhatsApp
app's fieldnames unrenamed, and since the endpoint filling them is now the app's own, the
contract and the query behind it share one vocabulary. Keeping that dialect would have
encoded one host's history into a shared package; a shim to undo it would have been a
translation layer nobody deletes.

A pure DocType shape isn't achievable, and `types.ts` says so rather than pretending:
`reactions[]`, `file_name`/`file_size`, the rendered `template`/`header`/`footer`/`buttons`
and the `reply_*` fields need reaction folding, a `File` join, variable substitution and
linked-document resolution. The interface is split into two labelled groups — **DocType
fields** and **server-derived** — because which group a field is in tells you where to look
when it's wrong.

**Host-specific data arrives as arguments, not hooks.** Two things in the old endpoints
genuinely were CRM-specific. The obvious fix was `frappe.get_hooks` callbacks; both are
better as arguments.

`get_from_name()` was deleted rather than hooked. It reads only the reference
doctype/docname, so across a whole fetch it resolves to *one string* — and the rule it feeds
(outgoing → "You", incoming → the contact) is presentation the client can already decide
from `direction`. A hook would have bought indirection to compute a known constant. It's the
`senderName` prop now, and `from_name`/`reply_to_from` are gone from the wire.

The Deal→Lead union became the `references` argument. A host decides what a conversation
spans; the endpoint checks `has_permission("read")` on every pair it's handed. That's
*stronger* than a hook — a registered resolver is trusted to return a safe scope, an
argument is assumed hostile and checked.

**`frappe-ui` is a peer, never a dependency** — see the section above for the failure mode.
Worth stating plainly because the work started from "add frappe-ui to the whatsapp app" and
the answer was the opposite.

**A note on `FP2`.** `@framework/ui`'s PHILOSOPHY scopes FP2 ("the host owns fetching") to
*list-view controls* — SortBy, Filter, ColumnSettings, QuickFilter. It does not forbid a
composable from fetching, and the closest precedents do exactly that: `useNotifications`
owns a `createListResource`, `useActivityTimeline` a `createResource`. Reading FP2 as a
blanket rule is what kept this package fetch-free for longer than it should have been.

## Not included

- No emoji picker. Reactions use a small fixed emoji bar; typing emoji is the OS keyboard's job.
- No i18n. Strings are plain English; user-facing chrome is exposed as props with English
  defaults so a host can override.
- No account or settings management — that stays in the host app for now.
- No socket of its own. `useMessages()` uses the host's, via `provide("socket", …)` or a
  `$socket` global; without one, live updates are simply off.
- No toasts or error dialogs. Failures land on the controller's `error` for the host to render.
