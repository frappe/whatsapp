import { computed, ref } from "vue";

interface SortableOptions {
  ids: () => string[];
  /** `index` counts the list without the moved item. */
  move: (id: string, index: number) => void;
  disabled?: () => boolean;
}

/**
 * Native HTML5 drag by a handle. Rows hold inputs, so a row is draggable only while its handle is
 * pressed. While dragging, `order` already shows the drop, so the other rows make room (with a
 * TransitionGroup) and the dragged row stays dimmed where it will land.
 */
export function useSortable({ ids, move, disabled = () => false }: SortableOptions) {
  const armed = ref<string | null>(null);
  const dragging = ref<string | null>(null);
  const target = ref<number | null>(null);

  const order = computed(() => {
    const all = ids();
    if (!dragging.value || target.value === null) return all;
    const rest = all.filter((id) => id !== dragging.value);
    rest.splice(target.value, 0, dragging.value);
    return rest;
  });

  function handle(id: string) {
    return {
      onPointerdown: () => !disabled() && (armed.value = id),
      onPointerup: () => (armed.value = null),
      onKeydown: (event: KeyboardEvent) => {
        if (!event.altKey || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
        event.preventDefault();
        step(id, event.key === "ArrowUp" ? -1 : 1);
      },
    };
  }

  function row(id: string) {
    return {
      draggable: armed.value === id,
      onDragstart: (event: DragEvent) => start(event, id),
      onDragover: (event: DragEvent) => over(event, id),
      onDrop: (event: DragEvent) => {
        event.preventDefault();
        finish();
      },
      onDragend: reset,
    };
  }

  /** Move up and Move down, for the keyboard. */
  function step(id: string, delta: -1 | 1) {
    const index = ids().indexOf(id) + delta;
    if (index >= 0 && index < ids().length) move(id, index);
  }

  function start(event: DragEvent, id: string) {
    if (armed.value !== id || !event.dataTransfer) return;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", id);
    liftedImage(event);
    requestAnimationFrame(() => {
      dragging.value = id;
      target.value = ids().indexOf(id);
    });
  }

  function over(event: DragEvent, id: string) {
    if (!dragging.value) return;
    event.preventDefault();
    if (id === dragging.value) return;
    const box = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const before = event.clientY < box.top + box.height / 2;
    const rest = ids().filter((each) => each !== dragging.value);
    target.value = rest.indexOf(id) + (before ? 0 : 1);
  }

  function finish() {
    const id = dragging.value;
    const index = target.value;
    reset();
    if (id && index !== null && index !== ids().indexOf(id)) move(id, index);
  }

  function reset() {
    armed.value = dragging.value = null;
    target.value = null;
  }

  return { order, dragging, handle, row, step };
}

/** The browser's drag image is a snapshot; a raised copy of the row makes it look lifted. */
function liftedImage(event: DragEvent) {
  const source = event.currentTarget as HTMLElement;
  const box = source.getBoundingClientRect();
  const copy = source.cloneNode(true) as HTMLElement;
  copy.classList.add("fb-lifted");
  copy.style.width = `${box.width}px`;
  document.body.appendChild(copy);
  event.dataTransfer!.setDragImage(copy, event.clientX - box.left, event.clientY - box.top);
  requestAnimationFrame(() => copy.remove());
}
