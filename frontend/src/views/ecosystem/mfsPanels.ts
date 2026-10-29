// XENO ECOSYSTEM, fifth stage — what the research pane shows of the saved results: the MFS comparison, the F1-F16 table, the SSS map of an MFS and the rejected candidates. Pure functions over the
// library the server returns (``/api/meos/mfs-library``); nothing is computed here that the saved results do not contain, and a candidate is never shown as an MFS.
import type { LibraryMfs, RejectedCandidate, SssPoint } from './routeGraph';

export interface FTableRow {
  condition_id: string; description: string; search_seeds: number[]; validation_seeds: number[]; candidate_retaining_sets: number; validated_mfs: number; rejected_candidates: number; near_miss_candidates: number; mfs_ids: string[]; cardinality: number[];
  history_role: string; m2_role: string; address_role: string; coupling_role: string; resource_role: string; renewal_role: string; sss_region_default_setting: string[]; observational_robustness: Array<number | null>; classification: string;
}
export interface RouteEquivalenceRow { a: string; b: string; level: number; class: string; verdict: string; differences: string[] }
export interface LibraryOut { mfs: LibraryMfs[]; rejected_candidates: RejectedCandidate[]; classification_table: FTableRow[]; route_equivalence: RouteEquivalenceRow[]; conditions: string[]; scenarios: string[]; controllers: string[]; levels: string[] }

export const CLASSES = ['NO_MFS', 'SINGLE_MFS', 'MULTIPLE_MFS', 'UNSTABLE_CANDIDATE', 'INCONCLUSIVE'] as const;
/** The count of conditions in each class (every class listed, also when it is 0). */
export const classCounts = (table: FTableRow[]): Record<string, number> => Object.fromEntries(CLASSES.map((c) => [c, table.filter((r) => r.classification === c).length]));

const f2 = (v: number | null | undefined, d = 2): string => (v === null || v === undefined ? '—' : v.toFixed(d));
export interface CompareRow { measure: string; a: string; b: string; differs: boolean }
/** The two MFS side by side: what each retains, what is the same and what differs. Equivalence is NOT stated here: it comes from the saved route-equivalence table (``equivalenceOf``). */
export function compareMfs(a: LibraryMfs, b: LibraryMfs): CompareRow[] {
  const row = (measure: string, x: string, y: string): CompareRow => ({ measure, a: x, b: y, differs: x !== y });
  const A = a.card, B = b.card;
  return [
    row('condition', a.condition, b.condition), row('route kind', a.route_kind, b.route_kind), row('cardinality', String(a.cardinality), String(b.cardinality)),
    row('retained', a.retained.join(', '), b.retained.join(', ')), row('removed', a.removed.join(', ') || 'none', b.removed.join(', ') || 'none'),
    row('retained paths', a.retained_paths.join(', '), b.retained_paths.join(', ')), row('lost paths', a.lost_paths.join(', ') || 'none', b.lost_paths.join(', ') || 'none'),
    row('energy use', f2(A?.energy_use), f2(B?.energy_use)), row('resource throughput', f2(A?.resource_throughput, 1), f2(B?.resource_throughput, 1)), row('recovery latency', f2(A?.recovery_latency, 0), f2(B?.recovery_latency, 0)),
    row('collapse share under perturbation', f2(A?.perturbation_collapse_share), f2(B?.perturbation_collapse_share)), row('history dependence', f2(A?.history_dependence), f2(B?.history_dependence)), row('Address dependence', f2(A?.address_dependence), f2(B?.address_dependence)),
    row('SSS region (default setting)', A?.sss_region ?? '—', B?.sss_region ?? '—'), row('observational robustness', f2(A?.observational_robustness), f2(B?.observational_robustness)),
    row('operational robustness', f2(A?.operational_robustness), f2(B?.operational_robustness)), row('addressability', f2(A?.addressability), f2(B?.addressability)), row('recoverability', f2(A?.recoverability), f2(B?.recoverability)),
  ];
}
/** The saved equivalence verdict for a pair of MFS, in either order; ``undefined`` when the pair was not compared (then the interface says so rather than inferring one). */
export const equivalenceOf = (table: RouteEquivalenceRow[], x: string, y: string): RouteEquivalenceRow | undefined => table.find((r) => (r.a === x && r.b === y) || (r.a === y && r.b === x));

export type CandidateMark = 'validated MFS' | 'rejected candidate' | 'near miss';
export interface CandidateRow { id: string; condition_id: string; retained: string[]; cardinality: number; mark: CandidateMark; search: string; validation: string; status: string }
/** Validated MFS and the rejected candidates in one list, each marked; a rejected candidate shows how often it persisted on the search seeds and on the validation seeds, kept apart. */
export function candidateRows(lib: Pick<LibraryOut, 'mfs' | 'rejected_candidates'>): CandidateRow[] {
  const out: CandidateRow[] = lib.mfs.map((m) => ({ id: m.id, condition_id: m.condition_id, retained: m.retained, cardinality: m.cardinality, mark: 'validated MFS', search: 'discovered (search seeds 1-5)', validation: 'survived (validation seeds 6-10)', status: 'validated' }));
  lib.rejected_candidates.forEach((c, i) => out.push({ id: `candidate ${c.condition_id}-${i + 1}`, condition_id: c.condition_id, retained: c.retained, cardinality: c.cardinality, mark: c.status === 'near miss' ? 'near miss' : 'rejected candidate',
    search: `${c.persists_in_search_seeds}/${c.search_seeds.length} search seeds`, validation: `${c.persists_in_validation_seeds}/${c.validation_seeds.length} validation seeds`, status: c.status }));
  return out;
}

export interface SssGrid { scales: number[]; sizes: number[]; speeds: number[]; cells: Map<string, string> }
const key = (p: SssPoint | { scale: number; size: number; speed: number }) => `${p.scale}/${p.size}/${p.speed}`;
/** The tested SSS points of an MFS as a grid (scale x size at each speed): the region at each tested point, and no value at a point that was not tested. */
export function sssGrid(points: SssPoint[]): SssGrid {
  const uniq = (xs: number[]) => [...new Set(xs)].sort((a, b) => a - b);
  return { scales: uniq(points.map((p) => p.scale)), sizes: uniq(points.map((p) => p.size)), speeds: uniq(points.map((p) => p.speed)), cells: new Map(points.map((p) => [key(p), p.region])) };
}
export const sssAt = (g: SssGrid, scale: number, size: number, speed: number): string | undefined => g.cells.get(key({ scale, size, speed }));
/** The statement the saved results support about ACTIVE against observation-sensitive points (used verbatim when no tested point is ACTIVE without being observation-sensitive). */
export const sssStatement = (points: SssPoint[]): string => (points.some((p) => p.region === 'ACTIVE') ? 'Some tested points are ACTIVE without being OBSERVATION-SENSITIVE.' : 'On the tested grid, all ACTIVE points were also observation-sensitive.');
