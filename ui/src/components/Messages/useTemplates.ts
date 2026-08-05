import { computed, reactive, ref, toValue, watch } from "vue";
import { createResource } from "frappe-ui";
import type {
  SendTemplateOverrides,
  TemplatesController,
  UseTemplatesOptions,
  WhatsAppTemplate,
} from "./types";

const MESSAGES_API = "whatsapp.whatsapp.api.messages";
const TEMPLATE_API =
  "whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template";

/**
 * The template controller: which templates may be sent from a DocType, and the two writes
 * that go with them.
 */
export function useTemplates(
  options: UseTemplatesOptions
): TemplatesController {
  const referenceDoctype = () => toValue(options.referenceDoctype) ?? "";
  const referenceDocname = () => toValue(options.referenceDocname) ?? "";
  const recipient = () => toValue(options.to) ?? "";

  // Failures a resource cannot hold: the guards applied before calling one.
  const guardError = ref<unknown>(null);

  const list = createResource({
    url: `${TEMPLATE_API}.get_sendable_templates`,
    makeParams: () => ({ reference_doctype: referenceDoctype() }),
  });

  const sendResource = createResource({ url: `${MESSAGES_API}.send_template` });
  const createTemplateResource = createResource({
    url: `${TEMPLATE_API}.create_template_and_push`,
  });

  const templates = computed<WhatsAppTemplate[]>(
    () => (list.data as WhatsAppTemplate[]) ?? []
  );
  const loading = computed<boolean>(() => Boolean(list.loading));
  const error = computed<unknown>(
    () =>
      guardError.value ??
      list.error ??
      sendResource.error ??
      createTemplateResource.error
  );

  async function reload() {
    try {
      await list.reload();
    } catch {
      // reported through `error`
    }
  }

  async function sendTemplate(
    templateName: string,
    overrides: SendTemplateOverrides = {}
  ): Promise<string | null> {
    guardError.value = null;
    const to = overrides.to ?? recipient();
    if (!to) {
      guardError.value = new Error(
        "Cannot send: useTemplates() was given no recipient (`to`)."
      );
      return null;
    }

    try {
      return (await sendResource.submit({
        template: templateName,
        to,
        reference_doctype: referenceDoctype(),
        reference_docname: overrides.referenceDocname ?? referenceDocname(),
      })) as string;
    } catch {
      // reported through `error`
      return null;
    }
  }

  async function createTemplate(
    template: Record<string, unknown>,
    accountName: string
  ): Promise<Record<string, unknown> | null> {
    guardError.value = null;
    try {
      const created = (await createTemplateResource.submit({
        doc_data: template,
        account_name: accountName,
      })) as Record<string, unknown>;
      await reload();
      return created;
    } catch {
      // reported through `error`
      return null;
    }
  }

  // A DocType change replaces the whole offering.
  watch(referenceDoctype, () => reload(), { immediate: true });

  // `reactive`, not a plain object: `v-bind` does not unwrap nested refs but `reactive`
  // does, so each member binds as a live value.
  return reactive({
    templates,
    loading,
    error,
    reload,
    sendTemplate,
    createTemplate,
  }) as TemplatesController;
}
