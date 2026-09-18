import { computed, reactive, ref, toValue, watch } from "vue";
import { call } from "frappe-ui";
import {
  MAPPING_SLOTS,
  type AccountController,
  type AppendAction,
  type FieldOption,
  type MappingSlot,
  type UseAccountOptions,
  type WhatsAppAccount,
} from "./types";

const DOCTYPE = "WhatsApp Account";
const OPTIONS_API =
  "whatsapp.whatsapp.doctype.whatsapp_account.whatsapp_account.get_append_field_options";

export function emptyAccount(): WhatsAppAccount {
  return {
    doctype: DOCTYPE,
    status: "Active",
    auto_read_receipts: 0,
    append_actions: [],
  };
}

export function emptyAppendAction(): AppendAction {
  return { append_to: "", trigger_on: "Incoming" };
}

export function useAccount(options: UseAccountOptions = {}): AccountController {
  const docName = ref(toValue(options.name) || "");
  const doc = ref<WhatsAppAccount>(emptyAccount());
  const loadedJson = ref("");
  const loading = ref(false);
  const saving = ref(false);
  const error = ref<unknown>(null);

  const fieldOptions = reactive(new Map<string, FieldOption[]>());
  const pendingOptions = new Map<string, Promise<void>>();

  const isNew = computed(() => !docName.value);
  const isDirty = computed(() => JSON.stringify(doc.value) !== loadedJson.value);

  function optionsKey(doctype: string, slot: MappingSlot) {
    return `${doctype}:${slot}`;
  }

  function optionsFor(doctype: string | undefined, slot: MappingSlot): FieldOption[] {
    if (!doctype) return [];
    return fieldOptions.get(optionsKey(doctype, slot)) ?? [];
  }

  function loadSlotOptions(doctype: string, slot: MappingSlot): Promise<void> {
    const key = optionsKey(doctype, slot);
    if (fieldOptions.has(key)) return Promise.resolve();
    const pending = pendingOptions.get(key);
    if (pending) return pending;

    const request = call<FieldOption[]>(OPTIONS_API, {
      target_doctype: doctype,
      slot,
    })
      .then((rows) => {
        fieldOptions.set(key, rows);
      })
      .finally(() => pendingOptions.delete(key));
    pendingOptions.set(key, request);
    return request;
  }

  async function loadOptions(doctype: string) {
    await Promise.all(MAPPING_SLOTS.map((slot) => loadSlotOptions(doctype, slot)));
  }

  function adopt(account: WhatsAppAccount) {
    doc.value = account;
    loadedJson.value = JSON.stringify(account);
  }

  async function reload() {
    if (!docName.value) {
      adopt(emptyAccount());
      return;
    }
    const name = docName.value;
    loading.value = true;
    error.value = null;
    try {
      const account = await call<WhatsAppAccount>("frappe.client.get", { doctype: DOCTYPE, name });
      // A slower load for a name the host has since moved on from must not win.
      if (docName.value !== name) return;
      adopt(account);
      const doctypes = new Set(account.append_actions.map((row) => row.append_to).filter(Boolean));
      await Promise.all([...doctypes].map(loadOptions));
    } catch (e) {
      if (docName.value === name) error.value = e;
    } finally {
      if (docName.value === name) loading.value = false;
    }
  }

  async function save(): Promise<string | null> {
    if (saving.value) return null;
    const name = docName.value;
    saving.value = true;
    error.value = null;
    try {
      const method = isNew.value ? "frappe.client.insert" : "frappe.client.save";
      const saved = await call<WhatsAppAccount>(method, { doc: doc.value });
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

  async function setAppendTo(row: AppendAction, doctype: string | null) {
    row.append_to = doctype ?? "";
    for (const slot of MAPPING_SLOTS) row[slot] = "";
    if (row.append_to) await loadOptions(row.append_to);
  }

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
    error,
    save,
    reload,
    setAppendTo,
    optionsFor,
  }) as AccountController;
}
