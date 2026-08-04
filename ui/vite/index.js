// Vite plugin for apps that consume @whatsapp/ui.
//
// This package has no build step: it ships raw .vue/.ts source that the host's
// bundler compiles in place, reached through a symlink or a path alias. That is
// what makes deduping necessary. When the bundler resolves a bare import such as
// `vue` or `frappe-ui` from a file inside this package, it walks up from the
// file's *realpath* — the package's own location — rather than from the host app.
// If it finds a copy there (or fails to collapse it with the host's), the app
// ends up running two copies: two Vue runtimes, and two frappe-ui/reka-ui
// module instances whose provide/inject keys no longer match, so context
// injection silently returns undefined. Forcing `resolve.dedupe` pins each of
// these to the host's single instance.
//
// Opt-in: add `whatsappUI()` to a consuming app's vite `plugins`. Pass
// `{ dedupe: [...] }` to extend the list with app-specific raw-source singletons.
//
// `dompurify` is deduped even though it is this package's own declared
// dependency, because the host has it too and a single copy is fine. The rule is
// about the host, not about ownership: a dependency the host does NOT have must
// never be listed here — deduping it would point resolution at a host copy that
// does not exist, and the import would fail.

const SINGLETONS = ["vue", "frappe-ui", "reka-ui", "dompurify"];

export default function whatsappUI(options = {}) {
	const extra = options.dedupe ?? [];
	const dedupe = [...new Set([...SINGLETONS, ...extra])];
	return {
		name: "whatsapp-ui-dedupe",
		config() {
			return {
				resolve: { dedupe },
			};
		},
	};
}
