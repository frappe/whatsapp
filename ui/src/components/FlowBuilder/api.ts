import { call } from "frappe-ui";
import type { FlowBuilderApi } from "./types";

const FLOWS = "whatsapp.whatsapp.flows";

export const frappeFlowApi: FlowBuilderApi = {
  list: (account) => call(`${FLOWS}.builder_reads.get_flow_list`, account ? { account } : {}),
  get: (name) => call(`${FLOWS}.builder_reads.get_flow_for_builder`, { name }),
  create: (args) => call(`${FLOWS}.authoring.create_flow`, { ...args }),
  copy: (name, flow_name) => call(`${FLOWS}.authoring.copy_flow`, { name, flow_name }),
  save: (name, flow_json, modified) => call(`${FLOWS}.authoring.save_flow`, { name, flow_json, modified }),
  remove: (name) => call(`${FLOWS}.authoring.delete_flow`, { name }),
  publish: (name) => call(`${FLOWS}.manage.publish_flow`, { name }),
  sync: (account_name) => call(`${FLOWS}.sync.sync_flows`, { account_name }),
};
