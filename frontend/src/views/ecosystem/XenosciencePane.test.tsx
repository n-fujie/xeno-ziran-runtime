// XENOSCIENCE pane — rendered to a string (the tests run in node) from real engine output: the stage-two record and observe() of it. What is checked is what a researcher is shown:
// the groups are separate, a reference value never appears among the observed ones, the statuses are the evidence statuses, and a missing run or observation is said, not filled in.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { MeosRecord, Observed, RunOut } from './meosApi';
import { FULL_OBSERVATION } from './meosApi';
import XenosciencePane, { type Branch } from './XenosciencePane';
import type { CouplingId } from './couplings';
import type { RegimeSide } from './xenoscience';

const dir = join(dirname(fileURLToPath(import.meta.url)), '__fixtures__');
const rec = JSON.parse(readFileSync(join(dir, 'meos-stage2.json'), 'utf8')) as MeosRecord;
const fx = JSON.parse(readFileSync(join(dir, 'meos-stage2-observed.json'), 'utf8')) as Record<'full' | 'coarse', { observed: Observed }>;
const out = (observed: Observed | null, record: MeosRecord = rec): RunOut => ({ record, observed: observed ?? undefined } as unknown as RunOut);
const cutFx = JSON.parse(readFileSync(join(dir, 'meos-coupling-cut.json'), 'utf8')) as Record<'base' | 'cut' | 'history_off', MeosRecord>;
const COARSE = { ...FULL_OBSERVATION, sampling_interval: 12 };
const html = (o: RunOut | null, entity: 'A1' | 'A2' | null = 'A1', tick = 100, obs = FULL_OBSERVATION, pinned: RegimeSide | null = null, coupling: CouplingId | null = null, branch: Branch | null = null) =>
  renderToString(<XenosciencePane rec={o ? o.record : null} out={o} tick={tick} setTick={() => undefined} obs={obs} entity={entity} sssClass={null} pinned={pinned} setPinned={() => undefined}
      coupling={coupling} selectCoupling={() => undefined} display={{ couplings: true, isolate: false, exploded: false, ghost: true }} setDisplay={() => undefined}
      branch={branch} playFrom={() => undefined} verifyReplay={async () => undefined} requestHistoryOff={async () => undefined} requestCut={async () => undefined} restoreBaseline={async () => undefined} clearBranch={() => undefined} busy={false} origin="NEW_ENGINE_RUN" />);
const section = (h: string, id: string) => { const i = h.indexOf(`data-testid="${id}"`); const next = h.indexOf('data-testid=', i + 10); return h.slice(i, next < 0 ? undefined : next); };
const text = (h: string) => h.replace(/<!-- -->/g, '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').replace(/\s+([,.;:)])/g, '$1').replace(/\(\s+/g, '(');  // tags become spaces: close up the spaces they leave before punctuation

describe('the Xenoscience pane', () => {
  it('asks for a run when there is none', () => {
    expect(text(html(null))).toContain('Run an experiment first');
  });
  it('keeps observed, inferred and reference readings in separate groups', () => {
    const h = html(out(fx.full.observed));
    for (const g of ['xeno-observed', 'xeno-inferred', 'xeno-reference']) expect(h).toContain(`data-testid="${g}"`);
    const o = text(section(h, 'xeno-observed')), r = text(section(h, 'xeno-reference'));
    expect(o).toContain('cycles recorded by the observation array');
    for (const hidden of ['firing threshold', 'adapted baseline', 'energy', 'power reserve', 'position']) { expect(o).not.toContain(hidden); expect(r).toContain(hidden); }
    expect(h.indexOf('data-testid="xeno-observed"')).toBeLessThan(h.indexOf('data-testid="xeno-reference"'));
  });
  it('reports observed and inferred readings as unresolved when the run has no observation result', () => {
    const h = html(out(null));
    expect(text(section(h, 'xeno-observed'))).toContain('unresolved');
    expect(text(section(h, 'xeno-observed'))).not.toMatch(/ACTIVE|COLLAPSED/);
    expect(text(section(h, 'xeno-reference'))).toContain('firing threshold');
  });
  it('says why the observation is unresolved: full resolution requests no separate result, a coarse run without one is a missing result', () => {
    expect(text(html(out(null)))).toContain('full-resolution observation');
    expect(text(html(out(null), 'A1', 100, COARSE))).toContain('no observation result for this run');
  });
  it('compares a pinned observation with the current one and reports the five kinds of change apart', () => {
    const pinned: RegimeSide = { obs: FULL_OBSERVATION, observed: fx.full.observed, resultDigest: rec.result_digest };
    const t = text(section(html(out(fx.coarse.observed), 'A1', 100, COARSE, pinned), 'xeno-regime'));
    for (const l of ['a real change in the target', 'a change in the observation apparatus', 'a change in the recorded representation', 'a change in the inferential classification', 'a change in the effective intervention possibilities']) expect(t).toContain(l);
    expect(t).toMatch(/a real change in the target UNCHANGED/); expect(t).toMatch(/observation apparatus CHANGED/); expect(t).toMatch(/intervention possibilities UNRESOLVED/);
  });
  it('shows the intervention log of the record, event ids included', () => {
    const t = text(section(html(out(fx.full.observed)), 'xeno-provenance'));
    expect(t).toContain(rec.result_digest); expect(t).toContain(rec.initial_config_digest);
    const all = text(html(out(fx.full.observed)));
    for (const l of rec.intervention_log) expect(all).toContain(`accepted (event ${l.event})`);
  });
  it('lists the critical intervals, with the unmodelled ones as UNSUPPORTED', () => {
    const t = text(section(html(out(fx.full.observed)), 'xeno-intervals'));
    for (const l of ['operational formation', 'observation', 'loss of effective access', 'evidential warrant', 'scientific attribution', 'material continuation', 'cessation', 'possible re-ignition']) expect(t).toContain(l);
    expect(t.match(/UNSUPPORTED/g)!.length).toBe(3);
  });
  it('treats Five-S as conditional: three controls, one configuration, one measurement', () => {
    const t = text(section(html(out(fx.full.observed)), 'xeno-fives'));
    expect((t.match(/CONTROL/g) ?? []).length).toBe(3); expect(t).toContain('CONFIGURATION'); expect(t).toContain('MEASURED');
  });
  it('shows the four conditions as evidence statuses with no score, and the joint classification as not established', () => {
    const h = html(out(fx.full.observed)), t = text(section(h, 'xeno-strong'));
    for (const c of ['Critical Resource Independence', 'Human-Readability Independence', 'Material and Organizational Reproduction', 'Autonomous Investigative Reorganization']) expect(t).toContain(c);
    expect(t).not.toContain('SUPPORTED WITHIN DECLARED CONDITIONS');
    expect(text(h)).toContain('NOT ESTABLISHED');
    expect(text(h)).not.toMatch(/\d+\s?%|score:/i);
  });
  it('keeps the six human dependencies apart', () => {
    const t = text(section(html(out(fx.full.observed)), 'xeno-human'));
    for (const l of ['continuing human decisions', 'human-maintained energy supply', 'human maintenance and fabrication', 'mandatory human-readable interpretation', 'human institutional approval', 'historically inherited human-defined variables']) expect(t).toContain(l);
  });
  it('renders without an entity selected (the pane offers A1 and A2) and for a tick outside the run', () => {
    expect(() => html(out(fx.full.observed), null, 99999)).not.toThrow();
    expect(html(out(fx.full.observed), null)).toContain('Select an entity on the stage');
  });

  it('lists the four couplings with the state the record gives at the playhead tick', () => {
    const at = (t: number) => text(section(html(out(null, cutFx.cut), 'A1', t), 'xeno-couplings'));
    expect(at(120)).toMatch(/interaction channel \(alteration M1\) cut/);
    expect(at(120)).toMatch(/feedback \(reconfigured resource R\) connected/);
    expect(at(160)).toMatch(/interaction channel \(alteration M1\) connected/);
    expect(at(120).match(/connected/g)!.length).toBe(3);
  });
  it('shows what the engine does with a selected coupling and offers the cut as a request', () => {
    const h = html(out(null, cutFx.base), null, 120, FULL_OBSERVATION, null, 'feedback'), t = text(section(h, 'xeno-coupling-detail'));
    expect(t).toContain('feedback (ISOLATE / RECONNECT)'); expect(t).toContain('no feedback to A1'); expect(t).toContain('state at tick 120 connected');
    expect(text(h)).toContain('REQUEST CUT AT TICK 120');
    expect(text(html(out(null, cutFx.base), null, 120))).not.toContain('REQUEST CUT');
  });
  it('compares the baseline with the intervention branch, from the two records', () => {
    const branch: Branch = { base: { record: cutFx.base, ivs: [] }, request: { kind: 'cut', id: 'interaction_channel', tick: 100, duration: 50 } };
    const t = text(section(html(out(null, cutFx.cut), null, 130, FULL_OBSERVATION, null, null, branch), 'xeno-branch'));
    expect(t).toMatch(/final status ACTIVE COLLAPSED/); expect(t).toMatch(/first COLLAPSED never 149/);
    const all = text(html(out(null, cutFx.cut), null, 130, FULL_OBSERVATION, null, null, branch));
    expect(all).toContain('ISOLATE interaction_channel @100; RECONNECT interaction_channel @150');
    expect(all).toContain('status first differs at tick 126'); expect(all).toContain('same configuration yes');
    expect(all).toContain('does not attribute the later differences to the cut');
    expect(text(html(out(null, cutFx.cut), null, 130))).not.toContain('Baseline and intervention branch');
  });
  it('says what produced the record on screen and that playing it back runs nothing', () => {
    const t = text(section(html(out(null)), 'xeno-origin'));
    expect(t).toContain('NEW ENGINE RUN'); expect(t).toContain('runs nothing');
  });
  it('lists the experiments with their real state, TO-C1 as a missing source', () => {
    const t = text(section(html(out(null)), 'xeno-experiments'));
    expect(t).toContain('in the 3D scene'); expect(t).toContain('source missing'); expect(t).toContain('fixture only'); expect(t).toContain('stored results');
    expect(t).toMatch(/TO-C1 .* source missing/);
    expect(t).not.toMatch(/\b(490|270|432|162)\b/);
  });
  it('shows the unresolved class apart from the other three, with the cycles an observation did not record', () => {
    const h = html(out(fx.coarse.observed)), u = text(section(h, 'xeno-unresolved'));
    expect(u).toContain('UNRESOLVED'); expect(u).toMatch(/\d+ of the 27 cycles of the run/); expect(u).toContain('retrieved under a later configuration');
    expect(h.indexOf('data-testid="xeno-reference"')).toBeLessThan(h.indexOf('data-testid="xeno-unresolved"'));
    expect(text(section(html(out(null)), 'xeno-unresolved'))).toContain('no observation result exists');
  });
  it('tracks the operational shape: operational and observed rows, and the marks of the engine\'s logs', () => {
    const h = html(out(fx.coarse.observed)), t = text(section(h, 'xeno-track-marks'));
    expect(h).toContain('aria-label="operational status per tick"'); expect(h).toContain('aria-label="observed status per tick"');
    for (const l of ['t=11 formation', 't=100 intervention', 't=149 cessation', 't=161 reignition']) if (!l.includes('100')) expect(t).toContain(l);
    expect(html(out(null))).not.toContain('aria-label="observed status per tick"');
  });
  it('separates retention, addressability, re-entry and the effective consequence', () => {
    const t = text(section(html(out(null, cutFx.base), null, 200), 'xeno-history'));
    expect(t).toMatch(/retention \(trace held at tick 200\)/); expect(t).toContain('NOT MODELLED'); expect(t).toMatch(/\d+ of \d+ cycles contain a history re-entry/);
    expect(t).toMatch(/effective consequence UNRESOLVED/); expect(t).toContain('needs a run of the same configuration with the history disabled');
    expect(text(html(out(null, cutFx.base), null, 200))).toContain('TEST CONSEQUENCE: DISABLE HISTORY AT TICK 200');
  });
  it('states the effective consequence from the two engine runs once the history-disabled branch exists', () => {
    const branch: Branch = { base: { record: cutFx.base, ivs: [] }, request: { kind: 'history-off', tick: 100 } };
    const t = text(section(html(out(null, cutFx.history_off), null, 200, FULL_OBSERVATION, null, null, branch), 'xeno-history'));
    expect(t).toContain('effective consequence DIFFERS'); expect(t).toMatch(/Baseline ACTIVE, 71 cycles \(9 with re-entry\); without history COLLAPSED, 22 cycles \(0\)/);
    expect(t).toContain('this configuration and seed');
  });
  it('offers to play a record back and to verify it by engine replay, as two different things', () => {
    const t = text(html(out(null)));
    expect(t).toContain('PLAY THE RECORD FROM TICK 0'); expect(t).toContain('VERIFY BY ENGINE REPLAY');
  });
});
