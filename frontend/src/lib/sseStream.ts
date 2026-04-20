/**
 * Shared SSE parser for the `fetch`-based streaming endpoints.
 *
 * Handles the boilerplate both chat pages (agent + quick search + conference
 * sidebar) were reimplementing:
 *   - getReader on the response body
 *   - UTF-8 decode with `{ stream: true }`
 *   - frame split on `\n\n`
 *   - per-line `data: ` prefix check + JSON parse
 *
 * Callers get `(data, rawLine)` and decide what to do with each event type.
 * Parse errors are swallowed — SSE is best-effort by design.
 */

export type SSEEvent = { type: string; [key: string]: unknown };

export async function parseSSEStream(
  response: Response,
  onEvent: (data: SSEEvent) => void,
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    while (buffer.includes("\n\n")) {
      const eventEnd = buffer.indexOf("\n\n");
      const eventText = buffer.slice(0, eventEnd);
      buffer = buffer.slice(eventEnd + 2);

      for (const line of eventText.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(line.slice(6)) as SSEEvent;
          onEvent(data);
        } catch {
          /* malformed frame — skip */
        }
      }
    }
  }
}
