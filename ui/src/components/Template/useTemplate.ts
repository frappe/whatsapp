import { computed, reactive, ref, toValue, watch } from "vue";
import { call } from "frappe-ui";
import { variableNames } from "./variables";
import type {
  TemplateController,
  TemplateIndicator,
  TemplateStatus,
  UseTemplateOptions,
  WhatsAppTemplateDoc,
} from "./types";

const DOCTYPE = "WhatsApp Template";
const COLUMNS_API =
  "whatsapp.whatsapp.doctype.whatsapp_template.whatsapp_template.get_doctype_columns";

const STATUS_THEME: Record<TemplateStatus, TemplateIndicator["theme"]> = {
  Pending: "orange",
  Approved: "green",
  Rejected: "red",
  Deleted: "gray",
};

// Meta edits only approved or rejected templates.
const LOCK_REASON: Partial<Record<TemplateStatus, string>> = {
  Pending: "Meta is reviewing this template. It can be edited once approved or rejected.",
  Deleted: "This template was deleted on Meta and can no longer be edited.",
};

export function emptyTemplate(): WhatsAppTemplateDoc {
  return {
    doctype: DOCTYPE,
    template_type: "Marketing",
    language: "en_US",
    header_type: "Text",
    status: "Pending",
    template_variables: [],
    buttons: [],
  };
}

export function useTemplate(options: UseTemplateOptions = {}): TemplateController {
  const docName = ref(toValue(options.name) || "");
  const doc = ref<WhatsAppTemplateDoc>(emptyTemplate());
  const loadedJson = ref("");
  const loading = ref(false);
  const saving = ref(false);
  const error = ref<unknown>(null);
  const fieldOptions = ref<string[]>([]);

  const isNew = computed(() => !docName.value);
  const isDirty = computed(() => JSON.stringify(doc.value) !== loadedJson.value);

  const indicator = computed<TemplateIndicator | null>(() => {
    if (isNew.value || isDirty.value) return { label: "Not Saved", theme: "orange" };
    const status = doc.value.status;
    return status ? { label: status, theme: STATUS_THEME[status] } : null;
  });

  const lockReason = computed(() => {
    if (isNew.value || !doc.value.whatsapp_template_id) return null;
    return LOCK_REASON[doc.value.status ?? "Pending"] ?? null;
  });
  const editable = computed(() => !lockReason.value);

  function adopt(template: WhatsAppTemplateDoc) {
    doc.value = template;
    loadedJson.value = JSON.stringify(template);
  }

  async function reload() {
    if (!docName.value) {
      adopt(emptyTemplate());
      return;
    }
    const name = docName.value;
    loading.value = true;
    error.value = null;
    try {
      const template = await call<WhatsAppTemplateDoc>("frappe.client.get", {
        doctype: DOCTYPE,
        name,
      });
      // A slower load for a name the host has since moved on from must not win.
      if (docName.value === name) adopt(template);
    } catch (e) {
      if (docName.value === name) error.value = e;
    } finally {
      if (docName.value === name) loading.value = false;
    }
  }

  async function save(): Promise<string | null> {
    if (saving.value) return null;
    if (lockReason.value) {
      error.value = lockReason.value;
      return null;
    }
    const name = docName.value;
    saving.value = true;
    error.value = null;
    mapVariablesToFields();
    try {
      const method = isNew.value ? "frappe.client.insert" : "frappe.client.save";
      const saved = await call<WhatsAppTemplateDoc>(method, { doc: doc.value });
      // The host may have moved on to another document while the save was in flight.
      if (docName.value !== name) return saved.name!;
      docName.value = saved.name!;
      await reload();
      return docName.value;
    } catch (e) {
      if (docName.value === name) error.value = e;
      return null;
    } finally {
      saving.value = false;
    }
  }

  // Done at save rather than in a watcher so a loaded document is not dirtied by it.
  function mapVariablesToFields() {
    for (const row of doc.value.template_variables) {
      row.variable_field = fieldOptions.value.includes(row.variable_name) ? row.variable_name : "";
    }
  }

  async function loadFieldOptions(doctype: string | undefined) {
    if (!doctype) {
      fieldOptions.value = [];
      return;
    }
    try {
      const columns = await call<string[]>(COLUMNS_API, { doctype });
      if (doc.value.reference_doctype === doctype) fieldOptions.value = columns;
    } catch (e) {
      error.value = e;
    }
  }

  // Unchanged names leave the rows untouched so a loaded document stays clean.
  function syncVariables() {
    const header = doc.value.header_type === "Text" ? doc.value.header_text : "";
    const names = variableNames(header, doc.value.message);
    const rows = doc.value.template_variables;
    if (names.length === rows.length && names.every((name, i) => rows[i].variable_name === name)) {
      return;
    }
    const existing = new Map(rows.map((row) => [row.variable_name, row]));
    doc.value.template_variables = names.map(
      (name) => existing.get(name) ?? { variable_name: name, variable_example: "" }
    );
  }

  watch(
    () => [doc.value.message, doc.value.header_text, doc.value.header_type],
    syncVariables
  );

  watch(() => doc.value.reference_doctype, loadFieldOptions, { immediate: true });

  watch(
    () => toValue(options.name) || "",
    (name) => {
      docName.value = name;
      reload();
    },
    { immediate: true }
  );

  return reactive({
    doc,
    loading,
    saving,
    isDirty,
    isNew,
    indicator,
    editable,
    lockReason,
    error,
    fieldOptions,
    save,
    reload,
  }) as TemplateController;
}
