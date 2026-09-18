import type { FieldNode, FormLayoutSchema } from "@framework/ui/components/FormLayout";
import TemplateBodyEditor from "./TemplateBodyEditor.vue";
import type { TemplateController } from "./types";

// Only documents a template can be sent from: child rows and singles have no record to bind to.
const REFERENCE_FILTERS = { istable: 0, issingle: 0 };

const VARIABLE_COLUMNS: FieldNode[] = [
  { fieldname: "variable_name", fieldtype: "Data", label: "Variable", readOnly: true },
  {
    fieldname: "variable_example",
    fieldtype: "Data",
    label: "Example",
    reqd: true,
    placeholder: "Meta reviews the template with this value",
  },
];

// Copy Code is not offered: `build_create_template_payload` drops it before the push.
const BUTTON_COLUMNS: FieldNode[] = [
  {
    fieldname: "button_type",
    fieldtype: "Select",
    label: "Type",
    options: "Quick Reply\nURL\nPhone Number\nVoice Call",
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

export function templateLayout(controller: TemplateController): FormLayoutSchema {
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
                  fieldname: "template_name",
                  fieldtype: "Data",
                  label: "Template name",
                  readOnly: true,
                  placeholder: "Derived from the label on save",
                  description: "Shared by every language variant of this template",
                },
                {
                  fieldname: "whatsapp_account",
                  fieldtype: "Link",
                  label: "WhatsApp Account",
                  options: "WhatsApp Account",
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
                  options: "WhatsApp Language",
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
          columns: [{ fields: [{ fieldname: "footer", fieldtype: "Data", label: "Footer" }] }],
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
                  hidden: doc.template_variables.length === 0,
                  childFields: VARIABLE_COLUMNS,
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
                  fieldname: "buttons",
                  fieldtype: "Table",
                  label: "Buttons",
                  childFields: BUTTON_COLUMNS,
                },
              ],
            },
          ],
        },
      ],
    },
  ];
  return editable ? schema : lockFields(schema);
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
