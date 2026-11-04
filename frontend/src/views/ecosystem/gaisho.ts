// GAISHO - Operational Shape Laboratory: the types of the engine's record and PURE READINGS of it (what the tab shows). Nothing here simulates, scores or attributes: a number is read from the record of an executed
// synthetic computational experiment, a shape is the engine's (built from the recorded surface of interventions), and the five levels of a candidate are shown as five separate records. The Gaisho attribution is never
// computed: without independent evidence it is UNRESOLVED, and an operational difference is not evidence of it (see PROHIBITED inferences in the record).

export const LEVELS = ['real_operation', 'operational_shape', 'conceptual_operational_shape', 'gaisho_operational_shape', 'gaisho_attribution'] as const;
export type LevelId = (typeof LEVELS)[number];
export type Unobserved = 'UNMEASURED' | 'INSTRUMENT_MISFIT' | 'SCALE_MISFIT' | 'TEMPORAL_MISFIT' | 'BOUNDARY_INVISIBLE' | 'IDENTIFICATION_UNRESOLVED';

export interface GaishoObservation { sensor_noise: number; sensor_channels: string[]; scale: number; temporal_window: number; speed: number; coupling: 'intervened' | 'passive'; resources: number; memory: boolean; environment: string; probe: number; boundary: string[] }
export const FULL_OBSERVATION: GaishoObservation = { sensor_noise: 0, sensor_channels: ['x', 'y', 'memory'], scale: 1, temporal_window: 40, speed: 1, coupling: 'intervened', resources: 10000, memory: true, environment: 'default', probe: 0, boundary: [] };

export interface Source { operation_digest: string; seeds: number; provenance: string }
export interface Vertex { id: string; x: number; y: number; z: number; sd: number | null; n: number; cell: [number, number]; source: Source }
export interface ShapeEdge { a: string; b: string; difference: number; source: Source }
export interface BranchPoint { x: number; y: number; z: number; from: [string, string]; source: Source }
export interface UnresolvedCell { id: string; x: number; y: number; reason: Unobserved; provenance: string }
export interface GaishoShape {
  domain: string; condition: string; snapshot: string; model_version: string; recorded: boolean; reason?: string; digest: string;
  projection: { kind: string; name: string; axes: { x: string; y: string; z: string }; chosen_by: string };
  nx?: number; ny?: number; vertices: Vertex[]; edges: ShapeEdge[]; cuts: ShapeEdge[]; branch: BranchPoint[]; unresolved: UnresolvedCell[]; weights?: Record<string, number> | null;
}
export type Relation = { status: 'IDENTIFIED'; value: number; sd: number; se: number; ci95: [number, number]; n: number; per_seed: number[] } | { status: Unobserved; value: null; n: number };
export interface Stat { mean: number | null; sd: number | null; se: number | null; n: number }
export interface CondResult { accuracy: Stat; accuracy_pre_shift: Stat; relations: Record<string, Relation>; seeds: number; operation_digest: string }
export interface Verdict { competitor: string; verdict: string; errors?: Record<string, number>; why?: string }
export interface AttributionTest { condition: string; operational_test: string; attribution: string; why: string; criterion?: Record<string, number> }
export interface LevelRecord { level: LevelId; state: string; evidence: string[]; note: string }
export interface NegativeResult { kind: string; condition?: string; relation?: string; class?: string; competitor?: string; why?: string; what?: string; mean?: number; ci95?: [number, number]; note?: string; domains_not_executed?: string[] }
export interface DomainStatus { completion: string; criteria: string; executed: boolean }
export interface GaishoRecord {
  model_version: string; executed: boolean; digest: string; figure_kind: string; note?: string; status: DomainStatus;
  spec: { domain: string; observation: GaishoObservation; seeds: number[]; conditions: string[] | null };
  axes?: { x: string; y: string };
  result?: { domain: string; title: string; seeds: number[]; observation: GaishoObservation; conditions: Record<string, CondResult & { snapshots: Record<string, { recorded: boolean; reason?: string }> }>; digest: string };
  shapes?: Record<string, Record<string, GaishoShape>>;
  structural_similarity?: Array<{ a: string; b: string; relations_compared: number; similarity: number | null }>;
  levels?: Record<string, Record<LevelId, LevelRecord>>;
  models?: { rows: Array<{ condition: string; verdicts: Verdict[] }>; rule: string; unit: string } | null;
  attribution_tests?: AttributionTest[];
  research_objects?: Record<string, Record<string, unknown>>;
  negative_results?: NegativeResult[];
  limits?: string;
  prohibited_inferences?: Array<{ premise: string; conclusion: string; reason: string }>;
}
export interface ChangeKinds { real_operation: string; recorded_observation: string; reconstructed_relation: { unobserved_in_one: string[]; unobserved_in_both: string[] }; display: string }
export interface ShapeReading {
  real_operation: string; weight_change: Record<string, number> | null; recorded_observation: { mean_abs_difference: number | null; expected_sampling_noise: number | null; reading: string | null };
  reconstructed_relation: { cuts_only_in_first: string[] | null; cuts_only_in_second: string[] | null; branch_points: [number, number] | null; note: string }; display: string; summary: string;
}
export interface TraceCell { id: string; cell: [number, number]; intervention: Record<string, number>; value: number; sd_across_seeds: number | null; se_of_mean: number | null; trials_per_cell_and_seed: number; seeds: number; expected_from_the_agents_weights: number | null; value_minus_expected: number | null; operation_digest: string; provenance: string }
export interface TraceEdge { a: string; b: string; kind: 'edge' | 'cut'; along: string; difference: number; expected_difference_from_weights: number | null; provenance: string }
export interface ConstructionOut {
  recorded: boolean; reason?: string; condition: string; snapshot: string; shape_digest: string; digest: string; rules: Record<string, string>; layers: Record<string, Record<'real_operation' | 'recorded_observation' | 'reconstructed_relation' | 'display', string>>; axes: { x: string; y: string; z: string };
  counts?: { grid: [number, number]; cells_expected: number; cells_recorded: number; cells_unresolved: number; cells_total: number; edges_expected_if_all_recorded: number; edges_drawn: number; cuts: number; branch_points: number };
  counts_consistent?: boolean; what_a_cell_is?: string; outcome_of_the_domain?: string | null; cells?: TraceCell[]; edges?: TraceEdge[]; weights_of_the_operation?: Record<string, number> | null; unresolved?: Array<{ id: string; reason: string }>;
  what_the_surface_carries?: { fitted_weights: Record<string, number>; weights_of_the_operation: Record<string, number>; rms_residual_of_the_fit: number; expected_sampling_rms: number; reading: string };
}
export interface ComparatorInfo { label: string; fits: string; parameters: number; information: string; history: boolean; nested_in: string | null }
export interface ComparatorsOut { comparators: Record<string, ComparatorInfo>; not_run: string[]; held_out: string; reading: string; rule: string; rows: Array<{ condition: string; verdicts: Array<{ competitor: string; verdict: string; errors?: Record<string, number> }> }> }
export interface Claim { id: string; status: 'SUPPORTED_IN_MODEL' | 'LIMITED_OR_NEGATIVE' | 'UNTESTED_PHILOSOPHICAL_HYPOTHESIS'; claim: string; rests_on: string }
export interface GaishoDomainInfo { title: string | null; conditions: string[]; x: string | null; y: string | null; snapshots: string[]; relations: string[]; max_seeds?: number; status: DomainStatus }
export interface GaishoSpecInfo {
  model_version: string; scope: string; source_status: string; domains: Record<string, GaishoDomainInfo>; observation_axes: string[]; observation_defaults: GaishoObservation; environments: string[];
  levels: Record<string, string>; level_states: string[]; provenance_classes: string[]; unobserved_classes: Unobserved[]; verdicts: string[]; figure_kinds: string[]; prohibited_inferences: Array<{ premise: string; conclusion: string; reason: string }>; limits: string; claims: Claim[];
}

export const UNOBSERVED_TEXT: Record<Unobserved, string> = {
  UNMEASURED: 'unmeasured: no channel or record exists for it',
  INSTRUMENT_MISFIT: 'instrument misfit: the instrument cannot resolve it',
  SCALE_MISFIT: 'scale misfit: the grid is coarser than the feature',
  TEMPORAL_MISFIT: 'temporal misfit: the window or the speed cannot hold it',
  BOUNDARY_INVISIBLE: 'boundary-invisible: it lies outside the observation boundary',
  IDENTIFICATION_UNRESOLVED: 'identification unresolved: the coupling does not separate the axes',
};

export const FIGURE_KIND_TEXT: Record<string, string> = {
  CONCEPTUAL_RECONSTRUCTION: 'Conceptual Reconstruction', SYNTHETIC_SIMULATION: 'Synthetic Simulation', EXECUTED_COMPUTATIONAL_EXPERIMENT: 'Executed Computational Experiment', PHYSICAL_MEASUREMENT: 'Physical Measurement', PHILOSOPHICAL_INTERPRETATION: 'Philosophical Interpretation',
};

export const num = (x: number | null | undefined, d = 3): string => (x === null || x === undefined ? '-' : x.toFixed(d));

/** One row per relation of a condition: the value with its 95 % interval, or the class of the reason it was not identified. */
export function relationRows(rec: GaishoRecord, cond: string): Array<{ name: string; status: string; text: string; value: number | null; ci: [number, number] | null }> {
  const c = rec.result?.conditions[cond];
  if (!c) return [];
  return Object.entries(c.relations).map(([name, r]) => r.status === 'IDENTIFIED'
    ? { name, status: r.status, text: `${num(r.value)} [${num(r.ci95[0])}, ${num(r.ci95[1])}] n=${r.n}`, value: r.value, ci: r.ci95 }
    : { name, status: r.status, text: UNOBSERVED_TEXT[r.status], value: null, ci: null });
}

/** The five levels of a candidate, in order, as five separate records (never merged into one state). */
export const levelRows = (rec: GaishoRecord, cond: string): LevelRecord[] => LEVELS.map((l) => rec.levels?.[cond]?.[l]).filter((x): x is LevelRecord => !!x);

export const shapeOf = (rec: GaishoRecord, cond: string, snapshot: string): GaishoShape | null => rec.shapes?.[cond]?.[snapshot] ?? null;
export const snapshotsOf = (rec: GaishoRecord): string[] => Object.keys(Object.values(rec.shapes ?? {})[0] ?? {});

/** The vertices an axis relation reads: the cells at the high and the low end of the axis it names. The relations of the laboratory that are not read from the surface (the correctness under do(W), the loss on a shift, a revision between two moments) have no cells and say so. */
export function relationSupport(relation: string, shape: GaishoShape): { cells: string[] | null; note: string } {
  const axis = /(^|_)(E|x)$/.test(relation) && !/^revision/.test(relation) ? 'x' : /(^|_)(S|y)$/.test(relation) && !/^revision/.test(relation) ? 'y' : null;
  if (!axis || !shape.recorded || shape.nx === undefined || shape.ny === undefined) {
    return { cells: null, note: relation.startsWith('revision') ? 'a revision is the difference between two moments: select the two moments (before / after) to see it' : 'this relation is not read from the cells of one surface (it is measured by its own intervention runs)' };
  }
  const hi = axis === 'x' ? shape.nx - 1 : shape.ny - 1;
  const take = shape.vertices.filter((v) => v.cell[axis === 'x' ? 0 : 1] === 0 || v.cell[axis === 'x' ? 0 : 1] === hi);
  return { cells: take.map((v) => v.id), note: `the mean over the other axis of the response at the high end minus the low end of ${axis === 'x' ? shape.projection.axes.x : shape.projection.axes.y}` };
}

/** Construction data of one vertex: the cell, its value, the number of trials and seeds behind it and its provenance (every point is traceable to its source). */
export function constructionOf(shape: GaishoShape, id: string): { id: string; rows: Array<[string, string]> } | null {
  const v = shape.vertices.find((x) => x.id === id);
  if (v) {
    const edges = [...shape.edges, ...shape.cuts].filter((e) => e.a === id || e.b === id);
    return { id, rows: [['kind', 'vertex (a recorded cell)'], ['cell', `i=${v.cell[0]}, j=${v.cell[1]}`], ['x', `${num(v.x, 2)} (${shape.projection.axes.x})`], ['y', `${num(v.y, 2)} (${shape.projection.axes.y})`], ['z', `${num(v.z)} = the share of the cell's trials with the domain's outcome, averaged over ${v.source.seeds} seeds (sd across seeds ${num(v.sd)})`],
      ['trials per cell and seed', String(v.n)], ['provenance', v.source.provenance], ['operation digest', v.source.operation_digest], ['edges', `${edges.length} (${edges.filter((e) => e.difference >= 0.5).length} cut)`], ['shape digest', shape.digest.slice(0, 16)]] };
  }
  const u = shape.unresolved.find((x) => x.id === id);
  if (u) return { id, rows: [['kind', 'unresolved region (not recorded)'], ['x', num(u.x, 2)], ['y', num(u.y, 2)], ['class', u.reason], ['meaning', UNOBSERVED_TEXT[u.reason]], ['provenance', u.provenance]] };
  return null;
}

/** The figure <-> experiment-condition correspondence: for each condition drawn in the figure, the conditions it was produced under, the seeds and the digests. */
export function figureTable(rec: GaishoRecord): Array<{ condition: string; operation_digest: string; seeds: number; accuracy_pre_shift: string; shapes: Array<{ snapshot: string; recorded: boolean; digest: string; vertices: number; unresolved: number; cuts: number; branch: number }> }> {
  const res = rec.result;
  if (!res) return [];
  return Object.entries(res.conditions).map(([condition, c]) => ({
    condition, operation_digest: c.operation_digest, seeds: c.seeds, accuracy_pre_shift: num(c.accuracy_pre_shift.mean),
    shapes: Object.entries(rec.shapes?.[condition] ?? {}).map(([snapshot, s]) => ({ snapshot, recorded: s.recorded, digest: s.digest.slice(0, 12), vertices: s.vertices.length, unresolved: s.unresolved.length, cuts: s.cuts.length, branch: s.branch.length })),
  }));
}

/** Negative results of a record, grouped by kind (kept, never filtered out). */
export function negativeCounts(rec: GaishoRecord): Array<[string, number]> {
  const m = new Map<string, number>();
  for (const n of rec.negative_results ?? []) m.set(n.kind, (m.get(n.kind) ?? 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}

/** The observation axes that differ from the fullest observation, as text. */
export function observationDiff(o: GaishoObservation): string[] {
  const out: string[] = [];
  (Object.keys(FULL_OBSERVATION) as Array<keyof GaishoObservation>).forEach((k) => {
    if (JSON.stringify(o[k]) !== JSON.stringify(FULL_OBSERVATION[k])) out.push(`${k}=${Array.isArray(o[k]) ? `[${(o[k] as string[]).join(',')}]` : String(o[k])}`);
  });
  return out;
}

/** The part of an observation that changes the realized operation itself (the rest only changes the record). */
export const operationPart = (o: GaishoObservation) => ({ temporal_window: o.temporal_window, environment: o.environment, probe: o.probe });

/** The completion statuses of the five domains, kept apart: one domain being executed never completes another. */
export const domainStatusRows = (info: GaishoSpecInfo): Array<{ id: string; title: string; completion: string; executed: boolean }> => Object.entries(info.domains).map(([id, d]) => ({ id, title: d.title ?? '(specified, not executed)', completion: d.status.completion, executed: d.status.executed }));

// ------------------------------------------------------------------------------------------------ the state of the tab and what it hands to the 3D scene
export interface GhostChoice { kind: 'none' | 'moment' | 'condition' | 'observation'; cond: string; snap: string }
export interface HistoryItem { id: number; label: string; spec: GaishoRecord['spec']; digest: string; restored: boolean | null }
export interface GaishoUi {
  domain: string; obs: GaishoObservation; seeds: number; picked: string[]; rec: GaishoRecord | null; recB: GaishoRecord | null; obsBName: string | null; cond: string; snap: string; ghost: GhostChoice;
  selected: string | null; relation: string | null; show: { surface: boolean; cuts: boolean; unresolved: boolean; branch: boolean }; history: HistoryItem[];
}
export const initialGaishoUi = (): GaishoUi => ({ domain: '001-knowledge', obs: { ...FULL_OBSERVATION }, seeds: 10, picked: [], rec: null, recB: null, obsBName: null, cond: '', snap: 'end', ghost: { kind: 'none', cond: '', snap: '' }, selected: null, relation: null,
  show: { surface: true, cuts: true, unresolved: true, branch: true }, history: [] });

/** Observation conditions the researcher can lay against the current one (each changes one thing of the ten axes; the realized operation changes only for temporal_window, environment and probe). */
export const OBS_PRESETS: Array<{ name: string; patch: Partial<GaishoObservation> }> = [
  { name: 'scale 2 (every second grid point)', patch: { scale: 2 } }, { name: 'scale 4 (every fourth grid point)', patch: { scale: 4 } },
  { name: 'temporal window 10', patch: { temporal_window: 10 } }, { name: 'temporal window 100', patch: { temporal_window: 100 } },
  { name: 'speed 3 (one snapshot in three)', patch: { speed: 3 } }, { name: 'instrument noise 0.3', patch: { sensor_noise: 0.3 } },
  { name: 'passive coupling', patch: { coupling: 'passive' } }, { name: 'no memory record', patch: { memory: false } },
  { name: 'cue axis outside the boundary', patch: { boundary: ['y'] } }, { name: 'resources: 30 cells', patch: { resources: 30 } },
  { name: 'observer probe 1.0 (perturbs the operation)', patch: { probe: 1 } }, { name: 'environment: harder evidence', patch: { environment: 'harder evidence (sigma 1.2)' } },
];

/** What the 3D scene draws: the shape of the chosen condition and moment of the record, the ghost the researcher chose (another moment, another condition, or the same condition seen through another observation) and the cells of the selected relation. */
export function frameOf(ui: GaishoUi): { shape: GaishoShape | null; ghost: GaishoShape | null; selected: string | null; support: string[] | null; show: GaishoUi['show'] } {
  const shape = ui.rec ? shapeOf(ui.rec, ui.cond, ui.snap) : null;
  let ghost: GaishoShape | null = null;
  if (ui.rec && ui.ghost.kind === 'moment') ghost = shapeOf(ui.rec, ui.cond, ui.ghost.snap);
  else if (ui.rec && ui.ghost.kind === 'condition') ghost = shapeOf(ui.rec, ui.ghost.cond, ui.snap);
  else if (ui.recB && ui.ghost.kind === 'observation') ghost = shapeOf(ui.recB, ui.cond, ui.snap);
  const support = shape && ui.relation ? relationSupport(ui.relation, shape).cells : null;
  return { shape, ghost, selected: ui.selected, support, show: ui.show };
}

/** A record of an experiment as downloadable JSON (the record is the whole specification: importing it re-runs the specification and checks the digest). */
export const exportRecord = (rec: GaishoRecord): string => JSON.stringify({ kind: 'gaisho-record', model_version: rec.model_version, spec: rec.spec, digest: rec.digest, figure_kind: rec.figure_kind, negative_results: rec.negative_results ?? [] }, null, 1);
export function parseRecord(text: string): { spec: GaishoRecord['spec']; digest: string } {
  const o = JSON.parse(text) as { kind?: string; spec?: GaishoRecord['spec']; digest?: unknown };
  if (o.kind !== 'gaisho-record' || !o.spec || typeof o.spec.domain !== 'string' || typeof o.digest !== 'string') throw new Error('not a GAISHO record');
  return { spec: o.spec, digest: o.digest };
}

/** The trace of one cell or edge of a shape, as the engine's construction record gives it (the intervention it stands for, the value, the trials and seeds, what the agent's weights predict, the edges it joins). */
export function cellTrace(t: ConstructionOut, id: string): { cell: TraceCell | null; edges: TraceEdge[]; unresolved: string | null } {
  const cell = t.cells?.find((c) => c.id === id) ?? null;
  return { cell, edges: (t.edges ?? []).filter((e) => e.a === id || e.b === id), unresolved: t.unresolved?.find((u) => u.id === id)?.reason ?? null };
}

/** The claims of the knowledge domain grouped as the research needs them apart: supported in the model, limited or negative, and untested philosophical hypotheses. */
export function claimGroups(claims: Claim[]): Array<{ status: Claim['status']; title: string; items: Claim[] }> {
  const titles: Record<Claim['status'], string> = { SUPPORTED_IN_MODEL: 'Supported by the executed experiments (this synthetic model only)', LIMITED_OR_NEGATIVE: 'Limits and negative results', UNTESTED_PHILOSOPHICAL_HYPOTHESIS: 'Philosophical hypotheses NOT tested here' };
  return (Object.keys(titles) as Claim['status'][]).map((status) => ({ status, title: titles[status], items: claims.filter((c) => c.status === status) }));
}
