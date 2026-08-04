# `frappe-ui` is a peer dependency, never a dependency

The work that produced this package started from the instruction *"add frappe-ui
to the whatsapp app"*, and the answer turned out to be the opposite: `frappe-ui`
and `vue` are declared as **`peerDependencies`** and must never be installed into
this package's `node_modules`. A future reader will ask exactly that question, so
this ADR records why.

The reason is how this package is consumed. It ships **raw `.vue`/`.ts` source**
with no build step (`README.md`), and a host links it by path, so the host's
bundler compiles these files in place. When the bundler resolves a bare import
like `vue` or `frappe-ui` from a file *inside* this package, it walks up from the
file's **realpath** — this package's own directory — not from the host app. If a
copy is sitting there, the app runs two: two Vue runtimes, so reactivity does not
cross the boundary, and two `frappe-ui`/`reka-ui` module instances, so
`provide`/`inject` keys stop matching and injected context silently resolves to
`undefined`. reka-ui, which `frappe-ui` builds on, threads context through nearly
every compound component, so this fails quietly and everywhere at once.

That failure mode is also what `FP1` costs if we get it wrong. The reason to
compose `frappe-ui` atoms rather than rebuild them is that they already ship the
ARIA, keyboard nav and focus management baseline (`P12`) — and a duplicated
reka-ui instance breaks precisely the injected context that delivers that
behaviour. Composing atoms is only safe on top of a single instance.

The mitigation is `resolve.dedupe` on the **host** side, pinning each shared
singleton to the host's one copy. `vite/index.js` exports a `whatsappUI()` plugin
that sets the list via `config()` so a host adds one plugin instead of
hand-maintaining an array; it mirrors `@framework/ui`'s `frameworkUI()` plugin
exactly.

**The asymmetry is the subtle part, and it cuts both ways.** `dompurify` is this
package's own real dependency *and* is deduped — because the host has it too, and
one copy is fine. The rule is about the **host**, not about ownership: a
dependency the host does **not** have must never be deduped, because deduping
points resolution at a host copy that does not exist and the import simply fails.
`@framework/ui` learned this with `leaflet` and `vuedraggable`, which live in its
own `node_modules`, resolve by realpath, and are deliberately absent from its
dedupe list. Before adding a name to `SINGLETONS`, ask whether the host has it —
not whether we do.

## Considered Options

- **Declare `frappe-ui` (and `vue`) as real dependencies.** Rejected: this is the
  failure being described. Installing them here guarantees the second instance;
  no amount of host configuration recovers from a package that has physically
  vendored its own Vue.
- **Vendor `frappe-ui` source into this package.** Rejected: same duplicate
  instance with worse ergonomics — it also freezes upstream fixes, forks the
  theming baseline, and puts us on the hook for maintaining atoms `FP1` exists to
  stop us from owning.
- **Rely on npm/yarn hoisting instead of `dedupe`.** Rejected: hoisting is a
  package-manager implementation detail, not a contract. It varies by manager and
  lockfile state, and the symptom when it fails (`inject` returning `undefined`)
  is far too quiet to debug from.

## Consequences

- `package.json` lists exactly one dependency, `dompurify`. Adding a second is a
  decision, not a routine — it must be checked against the asymmetry above.
- Running an install *inside* `apps/whatsapp/ui/` is a mistake, not a setup step.
  Its `node_modules` should stay empty of packages.
- Hosts must either add `whatsappUI()` to their vite `plugins` or replicate the
  `dedupe` list by hand. Skipping it does not fail loudly; it fails as broken
  popovers and dialogs.
- Because the host supplies `frappe-ui`, the host also picks its version. The
  peer range (`>=1.0.0-beta.16`) is the compatibility statement, and widening it
  is how we would support an older host.
