// XENOSCIENCE pane — rendered to a string (the tests run in node) from real engine output: the stage-two record and observe() of it. What is checked is what a researcher is shown:
// the groups are separate, a reference value never appears among the observed ones, the statuses are the evidence statuses, and a missing run or observation is said, not filled in.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { MeosRecord, Observed, RunOut } from './meosApi';
import { FULL_OBSERVATION } from './meosApi';
import XenosciencePane from './XenosciencePane';
import type { RegimeSide } from './xenoscience';

const dir = join(dirname(fileURLToPath(import.meta.url)), '__fixtures__');
const rec = JSON.parse(readFileSync(join(dir, 'meos-stage2.json'), 'utf8')) as MeosRecord;
const fx = JSON.parse(readFileSync(join(dir, 'meos-stage2-observed.json'), 'utf8')) as Record<'full' | 'coarse', { observed: Observed }>;
const out = (observed: Observed | null): RunOut => ({ record: rec, observed: observed ?? undefined } as unknown as RunOut);
const COARSE = { ...FULL_OBSERVATION, sampling_interval: 12 };
const html = (o: RunOut | null, entity: 'A1' | 'A2' | null = 'A1', tick = 100, obs = FULL_OBSERVATION, pinned: RegimeSide | null = null) =>
  renderToString(<XenosciencePane rec={o ? rec : null} out={o} tick={tick} setTick={() => undefined} obs={obs} entity={entity} sssClass={null} pinned={pinned} setPinned={() => undefined} />);
const section = (h: string, id: string) => { const i = h.indexOf(`data-testid="${id}"`); const next = h.indexOf('data-testid=', i + 10); return h.slice(i, next < 0 ? undefined : next); };
const text = (h: string) => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');

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
});
