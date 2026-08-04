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

## Not included

- No emoji picker. Reactions use a small fixed emoji bar; typing emoji is the OS keyboard's job.
- No i18n. Strings are plain English; user-facing chrome is exposed as props with English
  defaults so a host can override.
- No account or settings management — that stays in the host app for now.
- No socket of its own. `useMessages()` uses the host's, via `provide("socket", …)` or a
  `$socket` global; without one, live updates are simply off.
- No toasts or error dialogs. Failures land on the controller's `error` for the host to render.
