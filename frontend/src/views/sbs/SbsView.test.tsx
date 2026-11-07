// SBS view: the model functions against the SAVED records (docs/sbs/), and the panels' wording. The viewer computes the group share from measured positions; it must agree with the backend's saved record.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { components, meanSweeps, outcomeTable, type FramesFile, type Summary } from './model';
import { ComparisonTable, Evidence, Hysteresis, OutcomesTable, RecordsPanel, Scene } from './SbsView';

const docs = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..', 'docs', 'sbs');
const sum = JSON.parse(readFileSync(join(docs, 'sbs_records.json'), 'utf8')) as Summary;
const fr = JSON.parse(readFileSync(join(docs, 'sbs_frames.json'), 'utf8')) as FramesFile;
const txt = (h: string) => h.replace(/<!-- -->/g, '').replace(/&#x27;/g, "'");

describe('the viewer reads the saved records and agrees with them', () => {
  it('computes the same largest-group share and number of groups from the measured positions as the backend record, at the end of every recovery', () => {
    let checked = 0;
    for (const [seed, branches] of Object.entries(fr.worlds)) {
      const world = sum.worlds.find((w) => String(w.seed) === seed)!;
      branches.forEach((b, i) => {
        const last = b.frames[b.frames.length - 1];
        const c = components(last.x, fr.box);
        const saved = world.branches[i].reconfiguration.physical;
        expect(c.largestShare).toBeCloseTo(saved.largest_share, 10);
        expect(c.groups).toBe(saved.groups_tracked);
        // the saved positions are rounded to three decimals, so a pair exactly at the contact cut-off can fall on the other side: the bond count may differ by one pair (the share and the groups did not differ in any branch)
        expect(Math.abs(c.bonds - saved.bonds)).toBeLessThanOrEqual(1);
        checked++;
      });
    }
    expect(checked).toBe(18); // two worlds, nine branches each
  });
  it('shows only measured frames: every branch has the frames at the recorded interval, none added', () => {
    for (const branches of Object.values(fr.worlds)) for (const b of branches) {
      expect(b.frames.length).toBe(18); // 1500/250 intervention + 3000/250 recovery samples
      expect(b.frames.every((f, i) => i === 0 || Math.abs(f.t_steps - b.frames[i - 1].t_steps - 250) < 1e-6)).toBe(true);
    }
    expect(fr.note).toContain('not interpolated');
  });
  it('counts the outcomes of the records and the means of the sweeps', () => {
    const t = outcomeTable(sum.worlds);
    expect(t).toHaveLength(9);
    expect(t.every((r) => Object.values(r.counts).reduce((a, b) => a + b, 0) === sum.worlds.length)).toBe(true);
    const m = meanSweeps(sum.metastability.sweeps);
    expect(m.eps).toHaveLength(9);
    expect(m.up[0]).toBeLessThan(m.down[0]); // hysteresis at the weakest coupling
  });
});

describe('the panels state what the records are and are not', () => {
  it('names the six records of dissolution separately and marks the agentic one as not applicable', () => {
    const h = txt(renderToString(<RecordsPanel b={sum.worlds[0].branches[2]} ref_size={sum.worlds[0].reference_group_size} />));
    for (const k of ['physical', 'organizational', 'functional', 'attributional', 'agentic', 'observational']) expect(h).toContain(`<th>${k}</th>`);
    expect(h).toContain('NOT_APPLICABLE'); expect(h).toContain('never summed');
  });
  it('keeps UNRESOLVED as a verdict and says EQUIVALENT_WITHIN_MARGIN is not identity', () => {
    const h = txt(renderToString(<ComparisonTable s={sum} />));
    expect(h).toContain('UNRESOLVED'); expect(h).toContain('is not identity'); expect(h).toContain('Holm');
  });
  it('states the evidence boundary: new execution, no body in the substrate, ON Lab not reproduced, no claim of Simondonian individuation', () => {
    const h = txt(renderToString(<Evidence s={sum} />));
    expect(h).toContain('NEW EXECUTION'); expect(h).toContain('contains no body'); expect(h).toContain('ON Lab'); expect(h).toContain('not proof of Simondonian individuation');
  });
  it('renders the scene and the hysteresis plot from the data', () => {
    expect(renderToString(<Scene x={fr.worlds['1'][0].frames[0].x} box={fr.box} />)).toContain('<circle');
    expect(txt(renderToString(<Hysteresis m={sum.metastability} />))).toContain('not a demonstration of metastability');
    expect(txt(renderToString(<OutcomesTable worlds={sum.worlds} />))).toContain('The control is not at 100% persistence');
  });
});
