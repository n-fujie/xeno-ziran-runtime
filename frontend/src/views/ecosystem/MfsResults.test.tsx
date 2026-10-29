// XENO ECOSYSTEM, fifth stage — the saved-results panel renders the selector, the comparison, the F table, the candidates and the SSS map from a library, and keeps candidates apart from MFS.
// Rendered to a string (the tests run in node): the initial state is what a deep link gives.
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import MfsResults from './MfsResults';
import type { FTableRow, LibraryOut } from './mfsPanels';
import type { LibraryMfs } from './routeGraph';

const card = { preserved_operation: 'ACTIVE', energy_use: 119.08, resource_throughput: 107.5, recovery_latency: 11, perturbation_collapse_share: 0.4, history_dependence: 1, address_dependence: 0.72, observational_robustness: 0, sss_region: 'OBSERVATION-SENSITIVE', ranges_along_axes: null, operational_robustness: 0.5, addressability: 0.7, recoverability: 0.9 };
const mfs = (id: string, kind: string, retained: string[], pts: LibraryMfs['sss_points']): LibraryMfs => ({ id, condition_id: 'F14', condition: 'SSS scale 1.5, delayed M2 tap', features: {}, retained, removed: [], cardinality: retained.length, route_kind: kind, retained_paths: [], lost_paths: [], digest: 'd', card, sss_points: pts });
const row = (id: string, cls: string): FTableRow => ({ condition_id: id, description: `condition ${id}`, search_seeds: [1, 2, 3, 4, 5], validation_seeds: [6, 7, 8, 9, 10], candidate_retaining_sets: 2, validated_mfs: cls === 'MULTIPLE_MFS' ? 2 : 1, rejected_candidates: 0, near_miss_candidates: 0, mfs_ids: [`MFS-${id}-1`], cardinality: [8], history_role: 'necessary', m2_role: 'n/a', address_role: 'x', coupling_role: 'necessary', resource_role: 'x', renewal_role: 'x', sss_region_default_setting: ['OBSERVATION-SENSITIVE'], observational_robustness: [0], classification: cls });
const lib: LibraryOut = {
  mfs: [mfs('MFS-F14-1', 'history-mediated', ['A2', 'history'], [{ scale: 1, size: 1, speed: 1, region: 'OBSERVATION-SENSITIVE' }, { scale: 1.5, size: 1, speed: 1, region: 'COLLAPSED' }]), mfs('MFS-F14-2', 'M2-mediated', ['A2', 'm2_tap'], [])],
  rejected_candidates: [{ condition_id: 'F8', retained: ['A2'], cardinality: 1, status: 'failed the search criterion', found_by: [], search_seeds: [1, 2, 3, 4, 5], persists_in_search_seeds: 4, validation_seeds: [6, 7, 8, 9, 10], persists_in_validation_seeds: 1, per_validation_seed: [], discovered_in_search: true, survived_validation: false }],
  classification_table: [row('F14', 'MULTIPLE_MFS'), row('F8', 'SINGLE_MFS'), row('F9', 'NO_MFS')],
  route_equivalence: [{ a: 'MFS-F14-1', b: 'MFS-F14-2', level: 3, class: 'non-equivalent', verdict: 'differs in history dependence', differences: ['history dependence'] }], conditions: [], scenarios: [], controllers: [], levels: [],
};
const html = (initial: { mfs?: string; experiment?: string; sssmap?: string }, l: LibraryOut | null = lib) => renderToString(<MfsResults lib={l} initial={initial} seed={3} busy={false} onRun={() => undefined} />);

describe('the saved-results panel', () => {
  it('says what is missing when the library is not saved', () => {
    expect(html({}, null)).toContain('saved results are not on this server');
  });
  it('states the thesis, counts every class, and lists F1-F16-style rows with their classification', () => {
    const h = html({ mfs: 'MFS-F14-1' });
    expect(h).toContain('local to particular conditions'); expect(h).toContain('>NO_MFS 1<'); expect(h).toContain('>MULTIPLE_MFS 1<'); expect(h).toContain('>UNSTABLE_CANDIDATE 0<');
    expect(h).toContain('condition F9'); expect(h).toContain('<b>NO_MFS</b>');
  });
  it('selects the MFS a deep link names and compares it with another, stating the saved equivalence', () => {
    const h = html({ mfs: 'MFS-F14-1' });
    expect(h).toContain('data-testid="eco-mfs-compare"'); expect(h).toContain('history-mediated'); expect(h).toContain('M2-mediated');
    expect(h).toContain('non-equivalent'); expect(h).toContain('differs in history dependence');
  });
  it('lists a rejected candidate apart from the MFS, with search and validation counts, and keeps the F8 and F9 wording', () => {
    const h = html({});
    expect(h).toContain('rejected candidate (failed the search criterion)'); expect(h).toContain('4/5 search seeds'); expect(h).toContain('1/5 validation seeds');
    expect(h).toContain('F8 is not counted as a condition with multiple MFS');
    expect(h).toContain('Under the allowed reductions and specified preservation criterion, no validated inclusion-minimal retaining set was found.');
  });
  it('draws the SSS map of the named MFS from tested points only, with the fixed statement', () => {
    const h = html({ sssmap: 'MFS-F14-1' });
    expect(h).toContain('data-testid="eco-sss-map"'); expect(h).toContain('On the tested grid, all ACTIVE points were also observation-sensitive.'); expect(h).toContain('Blank cells were not tested.');
    expect(h).toContain('title="COLLAPSED"'); expect(h).toContain('title="not tested"'.replace('not tested', 'OBSERVATION-SENSITIVE'));
  });
  it('highlights the condition of an experiment link', () => {
    expect(html({ experiment: 'F9' })).toContain('data-focus="true"');
  });
});
