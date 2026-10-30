// XENO ECOSYSTEM, sixth stage — the repair panel renders the stress and action selectors, keeps the classes of action apart, shows the three horizons with the costs unweighted, the controller's decisions, the reachable-recovery strips and what the engine cannot do.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import RepairPanel from './RepairPanel';
import type { RepairActionSpec, RepairBlock, RepairLibraryOut, StressRow } from './meosApi';

const fx = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'meos-stage6-repair.json'), 'utf8')) as Record<string, RepairBlock>;
const act = (id: string, klass: 'A' | 'B' | 'C', status: RepairActionSpec['status'], mags: number[] = [], note = ''): RepairActionSpec => ({ id, class: klass, family: id.split('.')[0], label: `label of ${id}`, status, magnitudes: mags, magnitude_meaning: 'meaning', durations: [0], latency: '1 tick', side_effect: 'none', reversibility: 'reversible', declared_cost: { switching: '1 operation' }, note });
const row = (stress: string, label: string, cls: string, win: number[][], latest: number | null): StressRow => ({
  stress, label, family: 'coupling', classification_at_decision_tick_113: cls, classification_at_any_tested_tick: cls, flags: [], internal_reconfiguration: { effective: false, windows: [] }, world_single: { effective: win.length > 0, windows: win }, combined: { effective: false, windows: [] },
  minimum_effective: win.length ? [{ action: 'resource.pulse', magnitude: 0.5, ticks: [113] }] : [], timing_window_fragments: win, first_window: win[0] ?? null, earliest_effective_tick: win[0]?.[0] ?? null, latest_successful_repair_tick: latest, earliest_irreversible_tick: latest === null ? null : latest + 1,
  irreversible_from_first_tested_tick: latest === null, window_open_at_end_of_tested_range: false, tested_range_end: null, unrepaired_collapse_tick: 149, window_closes_before_collapse: latest !== null, reference_repair: null, failure_reasons_in_the_tested_grid: {}, near_miss: false,
});
const lib: RepairLibraryOut = {
  actions: [act('internal.m2_tap', 'A', 'implemented'), act('resource.pulse', 'B', 'implemented', [0.5, 1, 2, 4]), act('coupling.restore', 'B', 'implemented', [0.7, 1]), act('resource.redistribute', 'B', 'proxy', [0.06], 'diffusion stands in for redistribution'), act('coupling.bypass', 'B', 'not implemented', [], 'there is no spatial coupling path to bypass'), act('observation.sampling', 'C', 'implemented')],
  stresses: { 'coupling gain 0.5': { family: 'coupling', label: 'coupling weakened (gain 0.5)', onset: 100 }, 'history lost': { family: 'history', label: 'history lost', onset: 100 } }, controllers: ['none', 'fixed', 'rule_based', 'cost_aware', 'delayed', 'noisy'], failure_classes: [],
  horizons: { short: 180, medium: 300, long: 480 }, recovery_window: 30, decision_tick: 113, stress_tick: 100, has_results: true, results: null, refine: null, controller_results: null,
  final: { stress_table: [row('coupling gain 0.5', 'coupling weakened (gain 0.5)', 'externally repairable', [[101, 105], [108, 117], [124, 140]], 140), row('history lost', 'history lost', 'neither (under the tested actions)', [], null)], resource_non_monotonicity: { 'coupling gain 0.5': { effective_band: [0.6, 2.5], phases: [{ phase: 'insufficient intervention', from: 0.1, to: 0.5 }, { phase: 'effective recovery', from: 0.6, to: 2.5 }, { phase: 'overshoot', from: 2.6, to: 6 }] } } },
};
const html = (repair: RepairBlock | null = null, initial = {}, l: RepairLibraryOut | null = lib) => renderToString(<RepairPanel lib={l} repair={repair} initial={initial} busy={false} onRun={() => undefined} />);

describe('the repair panel', () => {
  it('says so when the library is missing', () => { expect(html(null, {}, null)).toContain('not available on this server'); });
  it('keeps the three kinds of recovery action apart in its words and its selectors, and offers no observation repair as a run action', () => {
    const h = html(null, { actions: [{ action: 'resource.pulse', magnitude: 1, duration: 0, t: 113 }] });
    expect(h).toContain('Internal reconfiguration'); expect(h).toContain('class A'); expect(h).toContain('class B'); expect(h).toContain('observation repair');
    expect(h).toContain('internal.m2_tap [A]'); expect(h).toContain('resource.pulse [B]'); expect(h).toContain('resource.redistribute [B, proxy]'); expect(h).not.toContain('observation.sampling [');  // class C is not offered as an action of a run
  });
  it('lists what the engine cannot do and the proxies, and never as something that can be run', () => {
    const h = html(); expect(h).toContain('coupling.bypass'); expect(h).toContain('there is no spatial coupling path to bypass'); expect(h).toContain('diffusion stands in for redistribution'); expect(h).not.toContain('coupling.bypass [');
  });
  it('shows the three horizons, the raw costs without a weighted total, the failure class and the decisions of a controller', () => {
    const h = html(fx.controller, { controller: 'rule_based' });
    expect(h).toContain('data-testid="eco-repair-result"'); expect(h).toContain('short (180)'); expect(h).toContain('long (480)'); expect(h).toContain('prevented'); expect(h).toContain('raw costs'); expect(h).toContain('normalised (by the undamaged run)');
    expect(h).not.toMatch(/weighted|total cost/i); expect(h).toContain('none: the run recovered'); expect(h).toContain('data-testid="eco-repair-decisions"'); expect(h).toContain('rule: M2 tap');
    const o = html(fx.overshoot); expect(o).toContain('OVERSHOOT'); expect(o).toContain('secondary collapse');
    expect(html(fx.no_action_available)).toContain('none available');
  });
  it('draws the reachable-recovery strips with one cell per tick, the windows with their gaps, and the pulse bands', () => {
    const h = html();
    expect(h).toContain('data-testid="eco-recovery-map"'); expect((h.match(/title="tick \d+:/g) ?? []).length).toBe(230 * 2);
    expect(h).toContain('latest successful repair tick 140'); expect(h).toContain('earliest irreversible 141'); expect(h).toContain('no tested action recovers it at any tested tick');
    expect(h).toContain('101-105, 108-117, 124-140'); expect(h).toContain('effective recovery 0.6-2.5'); expect(h).toContain('overshoot 2.6-6'); expect(h).toContain('not of the world');
  });
});
