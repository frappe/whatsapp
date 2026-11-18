import type { FieldNode, FormLayoutSchema, Section } from "@framework/ui/components/FormLayout";
import FlowButtonEditor from "./FlowButtonEditor.vue";
import TemplateBodyEditor from "./TemplateBodyEditor.vue";
import TemplateVariablesField from "./TemplateVariablesField.vue";
import { FLOW_BUTTON_CHROME, type FlowButtonChrome } from "./flowChrome";
import type { TemplateButtonRow, TemplateController } from "./types";

// Only documents a template can be sent from: child rows and singles have no record to bind to.
const REFERENCE_FILTERS = { istable: 0, issingle: 0 };

// Copy Code is not offered: `build_create_template_payload` drops it before the push.
const BUTTON_COLUMNS: FieldNode[] = [
  {
    fieldname: "button_type",
    fieldtype: "Select",
    label: "Type",
    options: "Quick Reply\nURL\nPhone Number\nVoice Call\nFlow",
    reqd: true,
  },
  { fieldname: "button_text", fieldtype: "Data", label: "Text", reqd: true },
  {
    fieldname: "url",
    fieldtype: "Data",
    label: "URL",
    dependsOn: 'eval:doc.button_type === "URL"',
    mandatoryDependsOn: 'eval:doc.button_type === "URL"',
  },
  {
    fieldname: "phone_number",
    fieldtype: "Data",
    label: "Phone number",
    dependsOn: 'eval:doc.button_type === "Phone Number"',
    mandatoryDependsOn: 'eval:doc.button_type === "Phone Number"',
  },
];

export function templateLayout(
  controller: TemplateController,
  flowChrome: Partial<FlowButtonChrome> = {}
): FormLayoutSchema {
  const { isNew, doc, editable } = controller;
  const schema: FormLayoutSchema = [
    {
      sections: [
        {
          hideLabel: true,
          hideBorder: true,
          columns: [
            {
              fields: [
                {
                  fieldname: "template_label",
                  fieldtype: "Data",
                  label: "Template label",
                  reqd: true,
                  placeholder: "Order shipped",
                },
                {
                  fieldname: "whatsapp_account",
                  fieldtype: "Link",
                  label: "WhatsApp Account",
                  options: "WA Account",
                  reqd: true,
                },
              ],
            },
            {
              fields: [
                {
                  fieldname: "template_type",
                  fieldtype: "Select",
                  label: "Template type",
                  options: "Utility\nMarketing\nAuthentication",
                  reqd: true,
                },
                {
                  fieldname: "language",
                  fieldtype: "Link",
                  label: "Language",
                  options: "WA Language",
                  reqd: true,
                  readOnly: !isNew,
                  description: isNew ? undefined : "Meta forbids changing the language once created",
                },
                {
                  fieldname: "reference_doctype",
                  fieldtype: "Link",
                  label: "Reference DocType",
                  options: "DocType",
                  filters: REFERENCE_FILTERS,
                  description: "Variables are filled from one document of this DocType when sent",
                },
              ],
            },
          ],
        },
        {
          hideLabel: true,
          columns: [
            {
              fields: [
                {
                  fieldname: "header_type",
                  fieldtype: "Select",
                  label: "Header type",
                  options: "Text\nImage\nDocument\nGIF\nVideo",
                },
              ],
            },
            {
              fields: [
                {
                  fieldname: "header_text",
                  fieldtype: "Data",
                  label: "Header text",
                  dependsOn: 'eval:doc.header_type === "Text"',
                  description: "At most one variable",
                },
                {
                  fieldname: "header_media",
                  fieldtype: "Attach",
                  label: "Header media",
                  dependsOn: 'eval:["Image", "Document", "Video", "GIF"].includes(doc.header_type)',
                },
              ],
            },
          ],
        },
        {
          hideLabel: true,
          hideBorder: true,
          columns: [
            {
              fields: [
                {
                  fieldname: "message",
                  fieldtype: "Small Text",
                  label: "Message",
                  reqd: true,
                  placeholder: "Hi {{first_name}}, your order is on its way.",
                  description: "Type {{ to insert a field of the reference DocType",
                  ui: {
                    component: TemplateBodyEditor,
                    props: { fields: () => controller.fieldOptions },
                  },
                },
              ],
            },
          ],
        },
        {
          hideLabel: true,
          hideBorder: true,
          columns: [
            {
              fields: [
                {
                  fieldname: "template_variables",
                  fieldtype: "Table",
                  label: "Variables",
                  description: "Meta reviews the template with these example values",
                  placeholder: "Example value",
                  hidden: doc.template_variables.length === 0,
                  ui: {
                    component: TemplateVariablesField,
                    props: { fields: () => controller.fieldOptions },
                  },
                },
              ],
            },
          ],
        },
        {
          hideLabel: true,
          hideBorder: true,
          columns: [{ fields: [{ fieldname: "footer", fieldtype: "Data", label: "Footer" }] }],
        },
        {
          hideLabel: true,
          hideBorder: true,
          columns: [
            {
              fields: [
                {
                  fieldname: "buttons",
                  fieldtype: "Table",
                  label: "Buttons",
                  childFields: BUTTON_COLUMNS,
                },
              ],
            },
          ],
        },
        ...flowButtonSections(controller, flowChrome),
      ],
    },
  ];
  return editable ? schema : lockFields(schema);
}

// A Flow button's settings don't fit a grid row, so each gets a section of its own below the grid.
function flowButtonSections(
  controller: TemplateController,
  chrome: Partial<FlowButtonChrome>
): Section[] {
  const untitled = chrome.untitledButton ?? FLOW_BUTTON_CHROME.untitledButton;
  return controller.doc.buttons
    .map((button, index) => ({ button, key: buttonKey(button, index) }))
    .filter(({ button }) => button.button_type === "Flow")
    .map(({ button, key }) => ({
      name: `flow-button:${key}`,
      label: button.button_text || untitled,
      collapsible: false,
      columns: [],
      part: {
        name: "flow-button",
        component: FlowButtonEditor,
        props: { controller, button, chrome, disabled: !controller.editable },
      },
    }));
}

function buttonKey(button: TemplateButtonRow, index: number): string {
  return String(button.name ?? button.__row_id ?? index);
}

function lockFields(schema: FormLayoutSchema): FormLayoutSchema {
  return schema.map((tab) => ({
    ...tab,
    sections: tab.sections.map((section) => ({
      ...section,
      columns: section.columns.map((column) => ({
        ...column,
        fields: column.fields.map((field) => ({ ...field, readOnly: true })),
      })),
    })),
  }));
}
