export const INTERRUPTED_RESPONSE_MESSAGE = "Response interrupted.";
export const FAILED_RESPONSE_MESSAGE = "Response failed.";

export function friendlyChatError(err: unknown): string {
  if (err instanceof DOMException && err.name === "AbortError") {
    return INTERRUPTED_RESPONSE_MESSAGE;
  }
  if (err instanceof TypeError) {
    return FAILED_RESPONSE_MESSAGE;
  }
  if (err instanceof Error) {
    const msg = err.message.trim();
    if (!msg || msg === "request_failed") {
      return FAILED_RESPONSE_MESSAGE;
    }
    if (msg.startsWith("{") || msg.includes('"detail"')) {
      return FAILED_RESPONSE_MESSAGE;
    }
    if (/^\d{3}\s/.test(msg) || msg.includes("status code")) {
      return FAILED_RESPONSE_MESSAGE;
    }
    if (msg.length > 120) {
      return FAILED_RESPONSE_MESSAGE;
    }
    return FAILED_RESPONSE_MESSAGE;
  }
  return FAILED_RESPONSE_MESSAGE;
}
