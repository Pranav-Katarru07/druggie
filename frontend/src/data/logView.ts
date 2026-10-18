// Tells server.py what's on screen so it prints the case details in its terminal.
// Fire-and-forget: the app works the same if the server isn't running.
export function logView(body: { event: string; case_id?: string; person_id?: string }) {
  fetch("/api/log", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => {});
}
