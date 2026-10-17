// View ↔ URL mapping. The view is the `view` query parameter, so every view has a shareable URL and browser
// Back/Forward move between views; other parameters (scenario, runtime, lang) are preserved.
import type { View } from './store/sim';

// View ids are matched case-insensitively, as the host's routing matches them (so a URL the host serves always
// renders a view); the app then writes the canonical lower-case id back into the URL.
const find = (v: string | null, allowed: readonly View[]) =>
  v === null ? undefined : allowed.find((a) => a === v.toLowerCase());

export function viewFromSearch(search: string, allowed: readonly View[], fallback: View): View {
  return find(new URLSearchParams(search).get('view'), allowed) ?? fallback;
}

export function searchForView(search: string, view: View, fallback: View): string {
  const q = new URLSearchParams(search);
  if (view === fallback) q.delete('view');
  else q.set('view', view);
  const s = q.toString();
  return s ? `?${s}` : '';
}

// The part of the URL that names no view: an unknown path (where the host serves the app for it) or an unknown
// `view` value. null when the URL addresses a view.
export function unknownRoute(pathname: string, search: string, allowed: readonly View[], base = import.meta.env.BASE_URL): string | null {
  // the app's own root: '/' on the host, or the sub-path it is served under (the browser build lives at /app/)
  const root = base.startsWith('/') ? base : '/';
  if (pathname !== root && pathname !== `${root}index.html`) return pathname;
  const v = new URLSearchParams(search).get('view');
  return v !== null && !find(v, allowed) ? `?view=${v}` : null;
}

export const APP_NAME = 'XENO ZIRAN SIMULATOR';
export const pageTitle = (viewName: string) => `${viewName} — ${APP_NAME}`;
