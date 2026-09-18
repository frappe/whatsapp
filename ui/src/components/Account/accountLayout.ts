import type { FormLayoutSchema } from "@framework/ui/components/FormLayout";
import type { AccountController } from "./types";

export function accountLayout(controller: AccountController): FormLayoutSchema {
  return [
    {
      sections: [
        {
          hideLabel: true,
          hideBorder: true,
          columns: [
            {
              fields: [
                {
                  fieldname: "account_name",
                  fieldtype: "Data",
                  label: "Account name",
                  placeholder: "Enter Account name",
                },
                {
                  fieldname: "status",
                  fieldtype: "Select",
                  label: "Status",
                  options: "Active\nInactive",
                },
                { fieldname: "app_id", fieldtype: "Data", label: "App ID", placeholder: "Enter App ID" },
              ],
            },
            {
              fields: [
                {
                  fieldname: "business_id",
                  fieldtype: "Data",
                  label: "Business ID",
                  placeholder: "Enter Business ID",
                },
                {
                  fieldname: "phone_id",
                  fieldtype: "Data",
                  label: "Phone ID",
                  placeholder: "Enter Phone ID",
                },
                {
                  fieldname: "access_token",
                  fieldtype: "Password",
                  label: "Access token",
                  placeholder: "Enter Access token",
                },
              ],
            },
          ],
        },
        {
          label: "Read Receipts",
          collapsible: false,
          columns: [
            {
              fields: [
                {
                  fieldname: "auto_read_receipts",
                  fieldtype: "Check",
                  label: "Auto Send Read Receipts",
                  // `isDirty` compares JSON, so the stored 0 | 1 must not become a boolean.
                  ui: {
                    on: {
                      change: (checked: boolean) => {
                        controller.doc.auto_read_receipts = checked ? 1 : 0;
                      },
                    },
                  },
                },
              ],
            },
          ],
        },
      ],
    },
  ];
}
