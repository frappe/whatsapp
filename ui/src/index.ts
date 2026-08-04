export * from "./components/Messages";
export * from "./utils";
// Messages/icons/* is deliberately not re-exported: those glyphs are the bubble's delivery
// ticks and attachment marks, not a public icon set. Reach them at
// "@whatsapp/ui/components/Messages/icons/CheckIcon.vue" if a host really needs one.
