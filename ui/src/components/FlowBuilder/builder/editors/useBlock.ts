import { computed } from "vue";
import { TEXT_LIMITS, updateBlock, type Block, type Json, type Screen } from "../../model";
import { useBuilder } from "../../context";
import { BlockActions } from "../actions";
import { fieldError } from "../problems";

/** What every block editor needs: its component, edits, limits and field errors. */
export function useBlock(props: { block: Block; screen: Screen }) {
  const builder = useBuilder();
  const { session, chrome, edit } = builder;
  const actions = new BlockActions(session, () => chrome.value);

  const component = computed(() => props.block.component);
  const type = computed(() => String(component.value.type));

  function value(property: string): string {
    const found = component.value[property];
    return typeof found === "string" ? found : "";
  }

  /** An empty optional text is left out of the JSON, as Meta does. */
  function set(property: string, next: Json | undefined) {
    edit((model) => updateBlock(model, props.block.uid, { [property]: next === "" ? undefined : next }));
  }

  function limit(property: string): number | undefined {
    return TEXT_LIMITS[type.value]?.[property];
  }

  function error(property: string): string | undefined {
    return fieldError(session.problems, chrome.value, {
      screen: props.screen.uid,
      item: props.block.uid,
      property,
    });
  }

  return { ...builder, actions, component, type, value, set, limit, error };
}
