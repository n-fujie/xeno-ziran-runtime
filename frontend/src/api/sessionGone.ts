// Definitive session loss, kept apart from transient transport failures.
//
// Sessions are ephemeral (expiry, close, owner reset, runtime restart). A session is *gone* only when the runtime
// answers 404 "no such session" for one of its routes; network errors, 502 / 503 (e.g. while a proxy waits for a
// restarting runtime) are transient. Once a session is gone every further request bound to it is refused locally,
// so no view keeps polling it, and listeners (the store) are told once.

const gone = new Set<string>();
const listeners = new Set<(sid: string) => void>();
const SESSION_ROUTE = /^\/api\/sessions\/([0-9a-f]{8,64})(?:[/?]|$)/;

/** The session a request path is bound to, if any (`/api/sessions/<sid>…`). */
export function sessionOf(path: string): string | null {
  return SESSION_ROUTE.exec(path)?.[1] ?? null;
}

/** Whether a response proves the session no longer exists (not a transient failure). */
export function provesGone(path: string, status: number, detail: unknown): boolean {
  return status === 404 && sessionOf(path) !== null && detail === 'no such session';
}

export function isGone(sid: string): boolean {
  return gone.has(sid);
}

export function markGone(sid: string): void {
  if (gone.has(sid)) return;
  gone.add(sid);
  for (const l of [...listeners]) l(sid);
}

export function onGone(listener: (sid: string) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Thrown, without a network request, for a request bound to a session already known to be gone. */
export class SessionGoneError extends Error {
  status = 404;
  constructor(public sid: string) {
    super('session gone');
  }
}

/** Test hook. */
export function _reset(): void {
  gone.clear();
  listeners.clear();
}
