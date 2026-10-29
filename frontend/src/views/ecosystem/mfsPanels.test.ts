// XENO ECOSYSTEM, fifth stage — the MFS comparison, the F table, the SSS map and the candidate list read the saved results faithfully and keep candidates apart from validated MFS.
import { describe, expect, it } from 'vitest';
import { candidateRows, classCounts, compareMfs, equivalenceOf, sssAt, sssGrid, sssStatement, type FTableRow, type RouteEquivalenceRow } from './mfsPanels';
import type { LibraryMfs, RejectedCandidate } from './routeGraph';

const base = { condition_id: 'F14', condition: 'SSS scale 1.5, delayed M2 tap', features: {}, removed: [], retained_paths: ['resource'], lost_paths: [], digest: 'x' };
const A: LibraryMfs = { ...base, id: 'MFS-F14-1', retained: ['A2', 'history'], cardinality: 2, route_kind: 'history-mediated', removed: ['m2_tap'], card: { preserved_operation: 'ACTIVE', energy_use: 119.08, resource_throughput: 107.56, recovery_latency: 11, perturbation_collapse_share: 0.4, history_dependence: 1, address_dependence: 0.72, observational_robustness: 0, sss_region: 'OBSERVATION-SENSITIVE', ranges_along_axes: null, operational_robustness: 0.5, addressability: 0.7, recoverability: 0.9 } };
const B: LibraryMfs = { ...base, id: 'MFS-F14-2', retained: ['A2', 'm2_tap'], cardinality: 2, route_kind: 'M2-mediated', removed: ['history'], card: { ...A.card!, history_dependence: null, perturbation_collapse_share: 0.6 } };
const rej: RejectedCandidate = { condition_id: 'F8', retained: ['A2'], cardinality: 1, status: 'failed the search criterion', found_by: ['x'], search_seeds: [1, 2, 3, 4, 5], persists_in_search_seeds: 4, validation_seeds: [6, 7, 8, 9, 10], persists_in_validation_seeds: 1, per_validation_seed: [false, false, false, true, false], discovered_in_search: true, survived_validation: false };

describe('MFS comparison', () => {
  it('shows what each retains and marks only the measures that differ', () => {
    const rows = compareMfs(A, B), by = Object.fromEntries(rows.map((r) => [r.measure, r]));
    expect(by['route kind']).toMatchObject({ a: 'history-mediated', b: 'M2-mediated', differs: true });
    expect(by['energy use']).toMatchObject({ a: '119.08', b: '119.08', differs: false });
    expect(by['history dependence']).toMatchObject({ a: '1.00', b: '—', differs: true });
    expect(by['collapse share under perturbation'].differs).toBe(true);
  });
  it('does not state an equivalence itself: it takes the saved verdict, in either order, or says there is none', () => {
    const tbl: RouteEquivalenceRow[] = [{ a: 'MFS-F14-1', b: 'MFS-F14-2', level: 3, class: 'non-equivalent', verdict: 'differs in history dependence', differences: ['history dependence'] }];
    expect(equivalenceOf(tbl, 'MFS-F14-2', 'MFS-F14-1')?.class).toBe('non-equivalent');
    expect(equivalenceOf(tbl, 'MFS-F14-1', 'MFS-F1-1')).toBeUndefined();
  });
});

describe('candidates versus validated MFS', () => {
  it('lists a rejected candidate apart from an MFS, with search and validation seeds kept separate', () => {
    const rows = candidateRows({ mfs: [A], rejected_candidates: [rej] });
    expect(rows[0]).toMatchObject({ id: 'MFS-F14-1', mark: 'validated MFS', status: 'validated' });
    expect(rows[1]).toMatchObject({ mark: 'rejected candidate', search: '4/5 search seeds', validation: '1/5 validation seeds', condition_id: 'F8' });
    expect(rows[1].id.startsWith('MFS')).toBe(false);
  });
  it('marks a near miss as a near miss, not as an MFS', () => {
    expect(candidateRows({ mfs: [], rejected_candidates: [{ ...rej, status: 'near miss' }] })[0].mark).toBe('near miss');
  });
});

describe('the F table and the SSS map', () => {
  it('counts every class, also an empty one', () => {
    const t = [{ classification: 'NO_MFS' }, { classification: 'SINGLE_MFS' }, { classification: 'SINGLE_MFS' }] as FTableRow[];
    expect(classCounts(t)).toEqual({ NO_MFS: 1, SINGLE_MFS: 2, MULTIPLE_MFS: 0, UNSTABLE_CANDIDATE: 0, INCONCLUSIVE: 0 });
  });
  it('builds the grid from tested points only', () => {
    const g = sssGrid([{ scale: 1, size: 1, speed: 1, region: 'OBSERVATION-SENSITIVE' }, { scale: 1.5, size: 1, speed: 1, region: 'COLLAPSED' }]);
    expect(g.scales).toEqual([1, 1.5]); expect(sssAt(g, 1.5, 1, 1)).toBe('COLLAPSED'); expect(sssAt(g, 2, 1, 1)).toBeUndefined();
  });
  it('states that every ACTIVE point was observation-sensitive only when no tested point is ACTIVE', () => {
    expect(sssStatement([{ scale: 1, size: 1, speed: 1, region: 'OBSERVATION-SENSITIVE' }])).toBe('On the tested grid, all ACTIVE points were also observation-sensitive.');
    expect(sssStatement([{ scale: 1, size: 1, speed: 1, region: 'ACTIVE' }])).toContain('ACTIVE without being');
  });
});
