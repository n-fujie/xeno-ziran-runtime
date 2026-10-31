// BODY / TOTAL OBSERVATION, Views B-H and export: every view reads the one session bundle the backend serves (same record ids, same body versions), a gap stays a gap, the classes cannot be merged, and the figure files keep their evidence.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { FigureOut, LegalBundle, SafetyOut } from './bodyApi';
import { isPng, pngAddText, pngTextChunks } from './png';
import { LEVELS, channelOf, integratedRows, recordOf, segments, statusRuns, validRange, type Session } from './session';
import { countStates, ViewB, ViewC, ViewD, ViewE, ViewF, ViewG, ViewH, ViewI } from './views';
import { SyntheticBanner, TABS } from './Workspace';

const fx = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'teoo-session.json'), 'utf8')) as { session: Session; figure: FigureOut; png_base64: string; safety: SafetyOut };
const s = fx.session;
const knee = 'joint.angle.knee_l';
const ids = new Set(s.records.map((r) => r.record_id));
const txt = (html: string) => html.replace(/<!-- -->/g, '');
const cited = (html: string) => [...html.matchAll(/rec-[0-9a-f]{8,}/g)].map((m) => m[0]);

describe('the session bundle is the one source of every view', () => {
  it('is SYNTHETIC, carries its banner text, and its record index equals its records', () => {
    expect(s.synthetic).toBe(true); expect(s.banner.length).toBeGreaterThan(10);
    expect(new Set(Object.keys(s.record_index))).toEqual(ids);
    expect(s.records.some((r) => r.provenance === 'MEASURED')).toBe(false);
    expect(s.body_versions).toEqual({ before: 1, after: Number(Object.keys(s.bodies).find((k) => k !== '1')) });
  });
  it('has the eight tabs A-H in order and a banner that offers no way to hide it', () => {
    expect(TABS.map((t) => t[0]).join('')).toBe('ABCDEFGHI');
    const h = renderToString(<SyntheticBanner />);
    expect(h).toContain('SYNTHETIC'); expect(h).toContain('cannot be hidden'); expect(h).not.toContain('<button'); expect(h).not.toContain('display:none');
  });
});

describe('selectors: a gap stays a gap', () => {
  const ch = channelOf(s.records[0], knee)!;
  it('breaks the line at every sample that is not MEASURED_VALID and keeps the status runs', () => {
    const segs = segments(ch, (t) => t, (v) => v);
    expect(segs.length).toBe(2); // the dropout splits the line in two; no line crosses it
    const runs = statusRuns(ch);
    expect(runs.some((r) => r.status !== 'MEASURED_VALID')).toBe(true);
    expect(runs.reduce((n, r) => n + (r.to - r.from + 1), 0)).toBe(ch.samples.length);
    expect(runs.every((r, i) => i === 0 || runs[i - 1].status !== r.status)).toBe(true);
  });
  it('computes the range from valid samples only and does not treat a missing value as zero', () => {
    const [lo, hi] = validRange(ch);
    const valid = ch.samples.filter((x) => x.status === 'MEASURED_VALID').map((x) => x.value as number);
    expect(lo).toBe(Math.min(...valid)); expect(hi).toBe(Math.max(...valid));
    expect(ch.samples.filter((x) => x.status !== 'MEASURED_VALID').every((x) => x.value === null)).toBe(true);
    expect(validRange({ ...ch, samples: ch.samples.map((x) => ({ ...x, status: 'MISSING', value: null })) })).toEqual([0, 1]);
  });
});

describe('Views B-G', () => {
  it('B draws the observed line in segments, the gap, the reconstruction band, and one status ribbon', () => {
    const h = renderToString(<ViewB s={s} variable={knee} onVariable={() => undefined} />);
    expect(h).toContain('data-testid="teoo-gap"'); expect(h).toContain('data-testid="teoo-band"'); expect(h).toContain('data-testid="teoo-estimate"');
    expect((h.match(/data-testid="teoo-segment"/g) ?? []).length).toBe(2); expect(h).toContain('RECONSTRUCTED_ESTIMATE'); expect(h).toContain('not an observation'); expect(h).toContain('a gap is not a zero');
    const other = renderToString(<ViewB s={s} variable={s.records[0].payload.channels!.find((c) => c.variable !== knee)!.variable} onVariable={() => undefined} />);
    expect(other).not.toContain('data-testid="teoo-band"'); // the reconstruction is shown only on the variable it reconstructs
  });
  it('C shows declared relations apart from observation relations and the relation field with what is not observed', () => {
    const h = renderToString(<ViewC s={s} t={12} />);
    expect(h).toContain('data-kind="declared"'); expect(h).toContain('data-kind="sensor"'); expect(h).toMatch(/not observed|unobserved|epistemic/i);
  });
  it('D shows the configuration in force at t, the declared targets with causes, and the revisions with who initiated them', () => {
    const h = txt(renderToString(<ViewD s={s} t={12} />));
    expect(h).toContain('configuration <b>v3</b>'); expect(h).toContain('5 of 7 declared targets observed');
    expect(h).toContain('data-target="tgt.ankle_l"'); expect(h).toContain('data-testid="teoo-revisions"'); expect(h).toContain('proposed'); expect(h).toContain('not demonstrated'); expect(h).toContain('not an acquisition');
    const t0 = txt(renderToString(<ViewD s={s} t={0} />));
    expect(t0).toContain('configuration <b>v1</b>'); expect(t0).toContain('UNMEASURABLE');
  });
  it('E keeps observation, intervention and counterfactual apart and makes no causal claim', () => {
    const h = txt(renderToString(<ViewE s={s} />));
    for (const k of ['OBSERVATION (before)', 'INTERVENTION', 'OBSERVATION (after)', 'COUNTERFACTUAL_MODEL']) expect(h).toContain(k);
    expect(h).toContain('association'); expect(h).toContain('not a causal effect'); expect(h).toContain(`body v${s.body_versions.before} → v${s.body_versions.after}`);
    expect(h).toContain(`v${s.body_versions.after}:`); expect(h).toContain('brace_knee_l');
    for (const id of cited(h)) expect(ids.has(id)).toBe(true);
  });
  it('F shows the method, assumptions, the interpolation and the information lost', () => {
    const h = txt(renderToString(<ViewF s={s} />));
    expect(h).toContain('data-testid="teoo-lost"'); expect(h).toContain('40'); expect(h).toContain('not an observation'); expect(h).toContain('unknown (the inputs are not synchronised), not zero');
    expect(h).toContain(s.reconstruction.record_id);
  });
  it('G shows the protocol, its class, reproduction and says that no real-world experiment was run', () => {
    const h = renderToString(<ViewG s={s} />);
    expect(h).toContain('reproduced identically'); expect(h).toContain('confirmatory'); expect(h).toContain('A real-world experiment has not been carried out'); expect(h).toContain('SYNTHETIC');
    expect(s.protocol.reproduction.identical).toBe(true);
  });
});

describe('View H: levels are kept, never added', () => {
  const rows = integratedRows(s, 12);
  it('has the seven levels and every row keeps its level, class and record id', () => {
    expect(LEVELS.map((l) => l.id)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(new Set(rows.map((r) => r.level))).toEqual(new Set([1, 2, 3, 4, 5, 6, 7]));
    for (const r of rows) { expect(r.cls).toBeTruthy(); if (r.level <= 4) expect(ids.has(r.record)).toBe(true); }
    expect(rows.filter((r) => r.level === 3).every((r) => r.cls === 'SYNTHETIC')).toBe(true);
    expect(rows.filter((r) => r.level === 7).every((r) => r.cls === 'unobserved')).toBe(true); // not observed is not absent, and is not given a record
    expect(rows.map((r) => r.level)).toEqual([...rows.map((r) => r.level)].sort((a, b) => a - b));
  });
  it('the unobserved rows follow the time: a different t gives the configuration in force at that time', () => {
    const at0 = integratedRows(s, 0).filter((r) => r.level === 7), at20 = integratedRows(s, 20).filter((r) => r.level === 7);
    expect(at0.length).toBeGreaterThan(at20.length);
    expect(at0.some((r) => r.note.includes('configuration v1'))).toBe(true); expect(at20.every((r) => r.note.includes('configuration v4'))).toBe(true);
  });
  it('renders the table with a level on every row and cites only records that exist', () => {
    const h = renderToString(<ViewH s={s} t={12} />);
    expect((h.match(/<tr data-level=/g) ?? []).length).toBe(rows.length); expect(h).toContain('never added together');
    for (const id of cited(h)) expect(ids.has(id)).toBe(true);
  });
  it('all views cite only records of the one session', () => {
    const all = [renderToString(<ViewB s={s} variable={knee} onVariable={() => undefined} />), renderToString(<ViewE s={s} />), renderToString(<ViewF s={s} />), renderToString(<ViewH s={s} t={5} />)];
    for (const h of all) for (const id of cited(h)) expect(ids.has(id)).toBe(true);
    expect(recordOf(s, s.intervention.record_id)?.kind).toBe('INTERVENTION'); expect(recordOf(s, s.intervention.counterfactual)?.kind).toBe('COUNTERFACTUAL_MODEL');
  });
});

describe('figure export: PNG helpers and the evidence a file keeps', () => {
  const png = Uint8Array.from(Buffer.from(fx.png_base64, 'base64'));
  it('reads the metadata chunk of a PNG made by the backend and checks the CRC of every chunk', () => {
    expect(isPng(png)).toBe(true);
    const md = JSON.parse(pngTextChunks(png)['teoo-metadata']) as FigureOut['metadata'] & { metadata_digest: string };
    expect(md.figure_id).toBe(fx.figure.metadata.figure_id); expect(md.evidence.watermarks).toContain('SYNTHETIC');
    const bad = png.slice(); bad[bad.length - 20] ^= 1;
    expect(() => pngTextChunks(bad)).toThrow(/CRC/);
  });
  it('writes a chunk that round-trips, and refuses non-ASCII text instead of changing it', () => {
    const base = png.slice(0, png.length); // already carries one chunk; add another
    const out = pngAddText(base, 'note', 'hello');
    expect(pngTextChunks(out).note).toBe('hello'); expect(pngTextChunks(out)['teoo-metadata']).toBe(pngTextChunks(png)['teoo-metadata']);
    expect(() => pngAddText(base, 'note', '脚')).toThrow(/ASCII/); expect(() => pngAddText(new Uint8Array(8), 'k', 'v')).toThrow(/not a PNG/);
  });
  it('the served figure has no issues, keeps its band and watermark text, and its metadata is ASCII', () => {
    const f = fx.figure;
    expect(f.issues).toEqual([]); expect(f.svg).toContain('teoo-band-bg'); expect(f.svg).toContain('data-class="SYNTHETIC"'); expect(f.metadata_ascii).toMatch(/^[\x20-\x7e]*$/);
    expect(f.metadata.evidence.band.some((b) => b.includes('none recorded'))).toBe(true);
    expect(f.svg).not.toContain('<script'); expect(f.svg).not.toContain('<image');
  });
  it('the safety information says that the production gate is closed and that human ingestion is not allowed', () => {
    expect(fx.safety.production_ready).toBe(false); expect(fx.safety.human_measurement_ingestion_allowed).toBe(false); expect(fx.safety.missing.length).toBeGreaterThan(0); expect(fx.safety.capabilities.length).toBe(8);
  });
});

describe('View I: AI legal governance', () => {
  const lg = (JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '__fixtures__', 'teoo-legal.json'), 'utf8')) as { legal: LegalBundle }).legal;
  const h = txt(renderToString(<ViewI b={lg} />));
  it('says that the catalogue is provisional and unverified, and that the institution is synthetic', () => {
    expect(h).toContain('data-testid="teoo-catalogue-notice"'); expect(h).toContain('PROVISIONAL catalogue'); expect(h).toContain('NOT verified against the original');
    expect(lg.synthetic).toBe(true); expect(lg.catalogue.verified_against_original).toBe(false); expect(h).toContain('a synthetic institution');
  });
  it('lists the fifteen guarantees with one state each and never adds them into a score', () => {
    expect((h.match(/data-guarantee="/g) ?? []).length).toBe(15); expect(h).toContain('the states are not added into a score');
    for (const a of Object.values(lg.assessments)) { expect(a.length).toBe(15); expect(a.map((x) => x.number)).toEqual(Array.from({ length: 15 }, (_, i) => i + 1)); expect(Object.values(countStates(a)).reduce((x, y) => x + y, 0)).toBe(15); }
  });
  it('shows INDETERMINATE for what is not observed and INAPPLICABLE only with a checked reason', () => {
    const part = lg.assessments['baseline, with some provisions not observed'], safe = lg.assessments['an institution for which irreversible harm is impossible'];
    expect(part.filter((x) => x.state === 'INDETERMINATE').length).toBe(lg.observation.not_observed_provisions.length); expect(part.every((x) => x.state !== 'ABSENT' || !lg.observation.not_observed_provisions.includes(x.provision))).toBe(true);
    for (const x of safe.filter((y) => y.state === 'INAPPLICABLE')) expect(x.reason).toContain('checked against the configuration');
    expect(h).toContain('not observed is not absent');
  });
  it('names a remedy path for every guarantee that is absent or partial', () => {
    for (const a of Object.values(lg.assessments)) for (const x of a.filter((y) => y.state === 'ABSENT' || y.state === 'PARTIAL')) expect(x.remedy_path.length).toBeGreaterThan(5);
    expect(h).toContain('data-testid="teoo-remedies"');
  });
  it('shows a stage without a legal basis as invalid, and a decision by the scoring system as not a legal decision', () => {
    const bad = lg.chains['decided by the scoring system'], good = lg.chains.valid;
    expect(good.assessment.valid_legal_decision).toBe(true); expect(bad.assessment.valid_legal_decision).toBe(false); expect(bad.assessment.first_invalid_stage).toBe('legal_fact');
    expect(h).toContain('legally valid decision: <b>yes</b>'); expect(txt(renderToString(<ViewI b={{ ...lg, chains: { x: bad } }} />))).toContain('legally valid decision: <b>no</b>');
    expect(good.chain.map((s) => s.stage).join()).toBe(['technical_event', 'data_representation', 'legal_fact', 'legal_classification', 'norm_selection', 'exception_handling', 'attribution', 'burden_of_proof', 'legal_decision', 'remedy'].join());
  });
  it('compares the interventions on one synthetic world and keeps fairness optimisation, deleting the score and the independent review apart', () => {
    const i = lg.interventions;
    expect(i['fairness optimisation only'].tpr_gap).toBeLessThan(i.baseline.tpr_gap - 0.2); expect(Math.abs(i['fairness optimisation only'].exclusion_persistence - i.baseline.exclusion_persistence)).toBeLessThan(0.1);
    expect(i['score deleted'].exclusion_qualified).toBeGreaterThan(i.baseline.exclusion_qualified + 0.1); expect(i.baseline.overturn_rate_of_wrongful).toBe(0); expect(i['independent review with authority and propagation'].overturn_rate_of_wrongful).toBeGreaterThan(0.1);
    expect(h).toContain('data-testid="teoo-interventions"');
  });
});
