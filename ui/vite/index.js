// Vite plugin for apps that consume @whatsapp/ui: add `whatsappUI()` to their `plugins`,
// optionally with `{ dedupe: [...] }` to extend the list.
//
// This package ships raw source, so a bare import inside it resolves from the package's own
// realpath, not the host's. Without deduping the app runs two Vue runtimes and two
// frappe-ui/reka-ui instances, whose provide/inject keys silently stop matching.
//
// Only list what the host also has: deduping a package the host lacks points resolution at a
// copy that does not exist.

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
