// A failed frappe-ui `call` carries the server's text on `messages`; `message` is only the method path.
export function serverErrorMessage(error: unknown): string {
  if (!error) return "";
  const { messages, message } = error as { messages?: string[]; message?: string };
  return messages?.length ? messages.join("\n") : (message ?? String(error));
}
