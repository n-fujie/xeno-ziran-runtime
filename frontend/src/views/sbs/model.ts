// SBS view: the measured records as the backend serves them (/api/sbs), and the few things the viewer itself derives from the measured positions.
// Nothing is interpolated: a frame is a measured state, and the viewer never shows a state that was not recorded.

export const R_BOND = 1.35; // the same contact cut-off as xzr/sbs/organisation.py
export const MIN_GROUP = 4;

export type Frame = { t_steps: number; phase: 'intervention' | 'recovery'; x: number[][] };
export type FrameBranch = { kind: string; level: number | null; frames: Frame[] };
export type FramesFile = { classification: string; protocol_digest: string; box: number; note: string; worlds: Record<string, FrameBranch[]> };

export type Branch = {
  kind: string;
  level: number | null;
  dissolution: {
    physical: { largest_share: number; components: number; bonds: number; groups_tracked: number };
    organizational: { best_overlap: number; reference_retained_in_best_group: number; reference_pieces: number[]; groups_now: number };
    functional_transmission: { ratio: number | null; lead_shift?: number; trail_shift?: number; why?: string };
    attributional: string;
    agentic: string;
    observational: string;
  };
  reconfiguration: {
    physical: { largest_share: number; groups_tracked: number; bonds: number };
    organizational: { best_overlap: number; reference_retained_in_best_group: number };
    outcome: string;
    transitions_of_cohesion: number;
    final_observation: Record<string, { ari_vs_true_partition: number; outcome_as_read_by_observer: string }>;
  };
};
export type World = { seed: number; reference_group_size: number; formation: { series: { t_steps: number; coupled: { largest_share: number }; uncoupled_control: { largest_share: number } }[] }; branches: Branch[] };
export type Comparison = { observation: string; protocol: string; pair: [string, string]; verdict: string; p_holm: number; brier_difference_y_minus_x: { mean: number; ci95: [number, number]; n: number } };
export type Summary = {
  classification: string;
  frozen_protocol_in_code: string;
  protocol_digest: string;
  source_revision: string;
  reproduce: string;
  seeds: { worlds: number[]; train: number[]; test: number[] };
  metastability: { sweeps: { eps: number[]; largest_share_up: number[]; largest_share_down: number[] }[]; hysteresis_area_mean: number; hysteresis_area_sd: number | null };
  comparison: { margin: number; evaluations: { observation: string; protocol: string; n_test_worlds: number; mean_brier: Record<string, number> }[]; comparisons: Comparison[]; models: Record<string, { label: string; parameters: number }> };
  worlds: World[];
};

export const branchLabel = (kind: string, level: number | null) => (kind === 'control' ? 'control (no intervention)' : `${kind} ${kind === 'decoupling' ? 'eps' : 'kT'} = ${level}`);

/** Connected components of the contact graph of measured positions in a periodic box. label -1: a component smaller than MIN_GROUP. */
export function components(x: number[][], box: number): { labels: number[]; largestShare: number; bonds: number; groups: number } {
  const n = x.length;
  const parent = Array.from({ length: n }, (_, i) => i);
  const find = (i: number): number => (parent[i] === i ? i : (parent[i] = find(parent[i])));
  let bonds = 0;
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      let dx = x[i][0] - x[j][0], dy = x[i][1] - x[j][1];
      dx -= box * Math.round(dx / box); dy -= box * Math.round(dy / box);
      if (Math.hypot(dx, dy) < R_BOND) { bonds++; parent[find(i)] = find(j); }
    }
  }
  const root = x.map((_, i) => find(i));
  const size = new Map<number, number>();
  root.forEach((r) => size.set(r, (size.get(r) ?? 0) + 1));
  const ids = [...size.keys()].filter((r) => (size.get(r) ?? 0) >= MIN_GROUP).sort((a, b) => (size.get(b) ?? 0) - (size.get(a) ?? 0));
  const labels = root.map((r) => ids.indexOf(r));
  return { labels, largestShare: Math.max(...size.values()) / n, bonds, groups: ids.length };
}

/** Outcome counts per branch over the worlds, in the order of the first world's branches. */
export function outcomeTable(worlds: World[]): { key: string; label: string; counts: Record<string, number> }[] {
  if (!worlds.length) return [];
  return worlds[0].branches.map((b, i) => {
    const counts: Record<string, number> = {};
    worlds.forEach((w) => { const o = w.branches[i].reconfiguration.outcome; counts[o] = (counts[o] ?? 0) + 1; });
    return { key: `${b.kind}-${b.level}`, label: branchLabel(b.kind, b.level), counts };
  });
}

/** Mean of the up and the down sweeps over the sweeps, per coupling. */
export function meanSweeps(sw: Summary['metastability']['sweeps']): { eps: number[]; up: number[]; down: number[] } {
  const eps = sw[0].eps;
  const mean = (k: 'largest_share_up' | 'largest_share_down') => eps.map((_, i) => sw.reduce((a, s) => a + s[k][i], 0) / sw.length);
  return { eps, up: mean('largest_share_up'), down: mean('largest_share_down') };
}
