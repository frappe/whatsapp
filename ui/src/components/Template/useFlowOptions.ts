import { call } from "frappe-ui";
import { LoadCache } from "./loadCache";
import type { FieldOption } from "../Account/types";
import type { FlowOutline, WhatsAppFlowOption } from "./types";

const MAPPING_API = "whatsapp.whatsapp.mapping";

export const EMPTY_OUTLINE: FlowOutline = { screens: [], entry_screens: {}, answers: [], sensitive: [] };

/** What a Flow button's editor lists: the Flows of the account's business, each Flow's outline, and field options. */
export function useFlowOptions() {
  const flows = new LoadCache<WhatsAppFlowOption[]>(async (account) => {
    const row = await call<{ business_id?: string | null }>("frappe.client.get_value", {
      doctype: "WA Account",
      fieldname: "business_id",
      filters: { name: account },
    });
    if (!row?.business_id) return [];
    return call("frappe.client.get_list", {
      doctype: "WA Flow",
      fields: ["name", "flow_name", "status", "endpoint_uri", "preview_url"],
      filters: { business_id: row.business_id },
      order_by: "flow_name asc",
      limit_page_length: 0,
    });
  });

  const outlines = new LoadCache<FlowOutline>(async (flow) => {
    const row = await call<{ outline?: string | FlowOutline | null }>("frappe.client.get_value", {
      doctype: "WA Flow",
      fieldname: "outline",
      filters: { name: flow },
    });
    const outline = typeof row?.outline === "string" ? JSON.parse(row.outline) : row?.outline;
    return { ...EMPTY_OUTLINE, ...outline };
  });

  const inputFields = new LoadCache<FieldOption[]>((reference_doctype, declared_type) =>
    call(`${MAPPING_API}.get_input_source_fields`, { reference_doctype, declared_type, txt: "" })
  );

  const targetFields = new LoadCache<FieldOption[]>((target_doctype, source_type) =>
    call(`${MAPPING_API}.get_mappable_fields`, { target_doctype, source_type, txt: "" })
  );

  return {
    clear() {
      for (const cache of [flows, outlines, inputFields, targetFields]) cache.clear();
    },
    flowsFor: (account: string | undefined) => (account ? flows.get(account) : null),
    outline: (flow: string | undefined) => (flow ? outlines.get(flow) : null),
    inputSourceFields: (referenceDoctype: string | undefined, declaredType: string) =>
      referenceDoctype ? inputFields.get(referenceDoctype, declaredType) : null,
    mappableFields: (targetDoctype: string | undefined, sourceType: string) =>
      targetDoctype && sourceType ? targetFields.get(targetDoctype, sourceType) : null,
  };
}
