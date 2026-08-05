// `~icons/*` are virtual modules resolved by unplugin-icons at the consumer's Vite build
// (`frappeui({ lucideIcons: true })`); this package ships source, so declare them for editors.
declare module "~icons/*" {
  import type { FunctionalComponent, SVGAttributes } from "vue";
  const component: FunctionalComponent<SVGAttributes>;
  export default component;
}
