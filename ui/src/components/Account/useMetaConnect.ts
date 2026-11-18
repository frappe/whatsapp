import { reactive, ref } from "vue";
import { call, toast } from "frappe-ui";
import { serverErrorMessage } from "../../utils/serverError";

const OAUTH_API = "whatsapp.whatsapp.oauth";
const RESULT_PARAM = "whatsapp_connect";
const ACCOUNT_PARAM = "whatsapp_account";

// Asked once per page load: false on a self-hosted or v1 site, which never asks Frappe Cloud.
let available: Promise<boolean> | undefined;

/** Connect with Meta, through Frappe Cloud's sign-in. Only a v2 site with Meta turned on can. */
export function useMetaConnect() {
  const canConnect = ref(false);
  const connecting = ref(false);

  available ??= call<boolean>(`${OAUTH_API}.can_connect_with_meta`).catch(() => false);
  available.then((value) => (canConnect.value = value));

  /** Sends the browser to Meta. With `account`, the sign-in reconnects that WA Account. */
  async function connect(account?: string) {
    connecting.value = true;
    try {
      const url = await call<string>(`${OAUTH_API}.initiate_connect`, {
        redirect_to: location.pathname + location.search,
        wa_account: account,
      });
      window.location.assign(url);
    } catch (error) {
      connecting.value = false;
      toast.error(serverErrorMessage(error));
    }
  }

  return reactive({ canConnect, connecting, connect });
}

export interface MetaConnectResult {
  /** `connected`, `reconnected`, or the error code the sign-in ended with */
  result: string;
  account?: string;
}

/**
 * Reads the result Meta's sign-in came back to this page with, takes it off the URL and shows it
 * as a toast. A host calls it once on load to open `account`. Null when the page did not come back
 * from a sign-in.
 */
export function readMetaConnectResult(): MetaConnectResult | null {
  const url = new URL(location.href);
  const result = url.searchParams.get(RESULT_PARAM);
  if (!result) return null;
  const account = url.searchParams.get(ACCOUNT_PARAM) ?? undefined;
  url.searchParams.delete(RESULT_PARAM);
  url.searchParams.delete(ACCOUNT_PARAM);
  history.replaceState(history.state, "", url);

  call<{ message: string; indicator: string }>(`${OAUTH_API}.get_connect_message`, {
    result,
    account,
  }).then(({ message, indicator }) => {
    // the server bolds the account name; a toast shows plain text
    const text = new DOMParser().parseFromString(message, "text/html").body.textContent ?? "";
    if (indicator === "green") toast.success(text);
    else toast.error(text);
  });
  return { result, account };
}
