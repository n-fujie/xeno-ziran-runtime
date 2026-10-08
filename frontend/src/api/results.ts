// Result loading for the static mirror. A large result file is also published as lossless sections (written by
// backend/scripts/export_static.py): each large section in its own content-addressed file, all small sections in one
// shared file. The section index (file, compressed size per section) is embedded in the build, so a view knows
// exactly which files it needs without a manifest round trip.
//
// Strategy, per file and view, by one deterministic rule (`plan`):
//   * whole file    — if the file is already loaded on this page, if it has no sections, or if the sections the view
//                     needs would come to at least RATIO of the whole file's compressed size;
//   * sections      — otherwise; every needed file is requested at once (one round of parallel requests).
// Sections are cached once per page load (and by the browser as immutable files) and reassembled in the file's own
// key order. The original file is untouched and stays the download (/api/experiments/<name>).

export type Select = { include?: string[]; exclude?: string[] };  // dotted section paths, e.g. 'systematic.raw'
export type Listing = { name: string; bytes: number; modified: number; sha256?: string; sections?: string }[];
/** Per sectioned file: compressed size of the whole file, the small-sections file, and every section in file order
 *  as [path, file (null = in the small-sections file), compressed size]. */
export type IndexEntry = { full: number; small: [string, number] | null; sections: [string[], string | null, number][] };
export type SectionIndex = Record<string, IndexEntry>;

/** Sections pay off only when they are clearly smaller than the whole file (they lose some shared compression). */
export const RATIO = 0.9;

/** Whether the section at `path` is needed for `sel` (a section is fetched whole, so overlap is enough). */
export function wanted(path: string[], sel?: Select): boolean {
  const p = path.join('.');
  const overlaps = (s: string) => p === s || p.startsWith(s + '.') || s.startsWith(p + '.');
  if (sel?.include && !sel.include.some(overlaps)) return false;
  return !sel?.exclude?.some((e) => p === e || p.startsWith(e + '.'));
}

export type Plan = { strategy: 'whole' | 'sections'; files: string[]; required: number; full: number };

/** The loading strategy for one file and selection (pure; `loaded`: the whole file is already on this page). */
export function plan(name: string, e: IndexEntry | undefined, sel: Select | undefined, loaded: boolean): Plan {
  const whole = `/api/experiments/${name}`;
  if (!e) return { strategy: 'whole', files: [whole], required: 0, full: 0 };
  const picked = e.sections.filter(([p]) => wanted(p, sel));
  const big = picked.filter(([, f]) => f !== null);
  const needSmall = e.small !== null && picked.some(([, f]) => f === null);
  const files = [...(needSmall && e.small ? [e.small[0]] : []), ...big.map(([, f]) => f as string)];
  const required = big.reduce((a, [, , c]) => a + c, 0) + (needSmall && e.small ? e.small[1] : 0);
  if (loaded || required >= RATIO * e.full) return { strategy: 'whole', files: [whole], required, full: e.full };
  return { strategy: 'sections', files, required, full: e.full };
}

/** Rebuild the object from (path, value) sections, in their order (the inverse of the exporter's split). */
export function assemble(parts: [string[], unknown][]): Record<string, unknown> {
  const obj: Record<string, unknown> = {};
  for (const [path, v] of parts) {
    if (path.length === 1) obj[path[0]] = v;
    else ((obj[path[0]] ??= {}) as Record<string, unknown>)[path[1]] = v;
  }
  return obj;
}

/** Reading a top-level section of the file that was not loaded is reported, never silently undefined. */
function guard(obj: Record<string, unknown>, name: string, all: Set<string>, report: (m: string) => void) {
  return new Proxy(obj, {
    get(t, k) {
      if (typeof k === 'string' && !(k in t) && all.has(k)) report(`result section "${k}" of ${name} was not loaded for this view`);
      return Reflect.get(t, k);
    },
  });
}

export function makeLoader(fetchJson: (url: string) => Promise<unknown>, index: SectionIndex,
  report: (m: string) => void = console.error, onPlan: (name: string, p: Plan) => void = () => {}) {
  const cache = new Map<string, Promise<unknown>>();
  const once = <T,>(url: string): Promise<T> => {
    let p = cache.get(url);
    if (!p) {
      p = fetchJson(url);
      p.catch(() => cache.delete(url));  // a failed read is retried on the next view load
      cache.set(url, p);
    }
    return p as Promise<T>;
  };
  return async function load<T>(name: string, sel?: Select): Promise<T> {
    const e = index[name];
    const p = plan(name, e, sel, cache.has(`/api/experiments/${name}`));
    onPlan(name, p);
    if (p.strategy === 'whole') return once<T>(p.files[0]);
    const got = await Promise.all(p.files.map((f) => once(f)));  // all requested before any is awaited
    const byFile = new Map(p.files.map((f, i) => [f, got[i]]));
    const small = new Map(((e.small ? byFile.get(e.small[0]) : undefined) as [string[], unknown][] | undefined ?? [])
      .map(([path, v]) => [path.join('.'), v]));
    const parts: [string[], unknown][] = e.sections.filter(([path]) => wanted(path, sel))
      .map(([path, f]) => [path, f === null ? small.get(path.join('.')) : byFile.get(f)]);
    return guard(assemble(parts), name, new Set(e.sections.map(([path]) => path[0])), report) as T;
  };
}
