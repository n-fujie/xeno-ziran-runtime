// GAISHO - Operational Shape Laboratory: the client side of /api/gaisho. A request carries a specification (a domain, an observation condition over the ten axes, seeds); the answer is the deterministic record of an
// executed SYNTHETIC computational experiment. Nothing here computes a result, a shape or an attribution, and the server stores nothing: a history is restored by running a record's specification again.
import type { BodySnnRecord, ChangeKinds, ComparatorsOut, ConstructionOut, CountermodelsOut, GaishoObservation, GaishoRecord, GaishoShape, GaishoSpecInfo, ShapeReading } from './gaisho';

async function call<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`/api/gaisho${path}`, body === undefined ? undefined : { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${path}: ${r.status} ${(await r.text()).slice(0, 200)}`);
  return r.json() as Promise<T>;
}
export interface GaishoRequest { domain: string; observation?: Partial<GaishoObservation>; seeds?: number[]; conditions?: string[] }
export const gaishoSpec = (): Promise<GaishoSpecInfo> => call<GaishoSpecInfo>('/spec');
export const gaishoRun = (req: GaishoRequest): Promise<GaishoRecord> => call<GaishoRecord>('/run', req);
export interface GaishoObsComparison { condition: string; same_realized_operation: boolean; observation_changed_the_operation: boolean; operation_part_first: Record<string, unknown>; operation_part_second: Record<string, unknown>; change_kinds: ChangeKinds; relations: Array<{ relation: string; first: number | string | null; second: number | string | null; kind: string; paired_difference?: { mean: number | null; ci95: [number, number] | null; detected: boolean | null; n: number } }>; digests: string[] }
export const gaishoCompareObservations = (req: GaishoRequest & { condition: string; first: Partial<GaishoObservation>; second: Partial<GaishoObservation> }): Promise<GaishoObsComparison> => call('/compare-observations', req);
export const gaishoFigure = (req: GaishoRequest & { snapshot?: string }): Promise<{ svg: string; digest: string; figure_kind: string }> => call('/figure', req);
export const gaishoRestore = (rec: Pick<GaishoRecord, 'spec' | 'digest'>): Promise<{ restored: boolean; same_digest: boolean; digest_recorded: string; digest_rerun: string }> => call('/restore', rec);
export type { GaishoShape };
export interface GaishoShapeComparison { comparable: boolean; reason?: string; cells_compared?: number; mean_abs_difference?: number | null; max_abs_difference?: number | null; mean_signed_difference?: number | null; cuts_only_in_first?: string[]; cuts_only_in_second?: string[]; unresolved_in_first_only?: string[]; unresolved_in_second_only?: string[]; branch_points?: [number, number] }
export const gaishoCompareShapes = (req: GaishoRequest & { first: { condition: string; snapshot: string }; second: { condition: string; snapshot: string } }): Promise<{ comparison: GaishoShapeComparison; reading: ShapeReading | null; digest: string }> => call('/compare-shapes', req);
export const gaishoConstruction = (req: GaishoRequest & { condition: string; snapshot: string }): Promise<ConstructionOut> => call('/construction', req);
export const gaishoComparators = (req: GaishoRequest): Promise<ComparatorsOut> => call('/comparators', req);
export const gaishoCountermodels = (): Promise<CountermodelsOut> => call('/countermodels', {});
export const gaishoBodySnn = (req: { condition: string; i: number; j: number; seeds?: number[] }): Promise<BodySnnRecord> => call('/body-snn', req);
