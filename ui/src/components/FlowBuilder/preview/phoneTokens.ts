import type { PreviewSettings } from "../types";

/**
 * WhatsApp's own colours for the phone. The phone is content, not builder chrome, so it does not
 * follow frappe-ui's tokens or the host's theme; it follows the preview's Theme setting.
 * Renderers read these as `var(--wa-*)`.
 */
const LIGHT = {
  bezel: "#e9edef",
  scrim: "#a9acae",
  avatar: "#0b7a4a",
  sheet: "#ffffff",
  card: "#ffffff",
  ink: "#111b21",
  "ink-2": "#54656f",
  "ink-3": "#8696a0",
  divider: "#e9edef",
  field: "#c5cbcf",
  accent: "#1daa61",
  "accent-ink": "#ffffff",
  "accent-soft": "#e7f8ee",
  link: "#008069",
  "button-off": "#f0f2f5",
  "button-off-ink": "#a5afb5",
  wallpaper: "#efeae2",
  "bubble-in": "#ffffff",
  "bubble-out": "#d9fdd3",
  skeleton: "#d1d7db",
};

type PhoneTokens = typeof LIGHT;

const DARK: PhoneTokens = {
  bezel: "#2a3942",
  scrim: "#0b1014",
  avatar: "#21c063",
  sheet: "#111b21",
  card: "#111b21",
  ink: "#e9edef",
  "ink-2": "#aebac1",
  "ink-3": "#8696a0",
  divider: "#222d34",
  field: "#3b4a54",
  accent: "#21c063",
  "accent-ink": "#0b141a",
  "accent-soft": "#103529",
  link: "#21c063",
  "button-off": "#202c33",
  "button-off-ink": "#566770",
  wallpaper: "#0b141a",
  "bubble-in": "#202c33",
  "bubble-out": "#005c4b",
  skeleton: "#3b4a54",
};

export function phoneStyle({ theme }: PreviewSettings): Record<string, string> {
  const tokens = theme === "dark" ? DARK : LIGHT;
  return Object.fromEntries(Object.entries(tokens).map(([name, value]) => [`--wa-${name}`, value]));
}
