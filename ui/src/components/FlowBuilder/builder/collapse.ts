/**
 * Espresso's accordion motion for `<Transition :css="false">`: height and opacity over 200ms on
 * its curve. Only the rows below move; nothing above the panel changes size.
 */
const MOTION = { duration: 200, easing: "cubic-bezier(.23, 1, .32, 1)" };

function reducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function animate(element: Element, from: number, to: number, done: () => void) {
  const panel = element as HTMLElement;
  if (reducedMotion()) return done();
  panel.style.overflow = "hidden";
  const animation = panel.animate(
    [
      { height: `${from}px`, opacity: from ? 1 : 0 },
      { height: `${to}px`, opacity: to ? 1 : 0 },
    ],
    MOTION
  );
  animation.onfinish = animation.oncancel = () => {
    panel.style.overflow = "";
    done();
  };
}

export const collapse = {
  onEnter: (element: Element, done: () => void) =>
    animate(element, 0, (element as HTMLElement).scrollHeight, done),
  onLeave: (element: Element, done: () => void) =>
    animate(element, (element as HTMLElement).offsetHeight, 0, done),
};
