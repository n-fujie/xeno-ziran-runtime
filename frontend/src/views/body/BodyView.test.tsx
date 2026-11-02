// BODY / TOTAL OBSERVATION, View A: the drawing is a function of the backend's data; the SYNTHETIC banner is enforced; every drawn class cites records that exist; a non-human body is drawn by the same code.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { searchForView, viewFromSearch } from '../../routing';
import type { Coverage, DemoResponse, TeooBody, TeooRecord } from './bodyApi';
import { BodyObservation, CONCEPT_NOTICE } from './BodyView';
import { CLASS_STYLE, describeTarget, layoutOf, marksOf, needsSyntheticBanner, targetsOfRef } from './bodyDraw';

const dir = join(dirname(fileURLToPath(import.meta.url)), '__fixtures__');
const demo = (JSON.parse(readFileSync(join(dir, 'teoo-demo.json'), 'utf8')) as { demo: DemoResponse }).demo;
const measured = JSON.parse(readFileSync(join(dir, 'teoo-measured.json'), 'utf8')) as { record: TeooRecord; coverage: Coverage; body: TeooBody; radial: TeooBody };
const html = (body: TeooBody, coverage: Coverage | null, records: TeooRecord[], selected: string | null = null) =>
  renderToString(<BodyObservation body={body} coverage={coverage} records={records} selected={selected} onSelect={() => undefined} />);

describe('View A: the SYNTHETIC display is enforced', () => {
  const h = html(demo.body, demo.coverage, demo.records);
  it('shows the banner and the watermark whenever a record is SYNTHETIC, and offers no control that could hide them', () => {
    expect(h).toContain('data-testid="teoo-synthetic-banner"'); expect(h).toContain('data-testid="teoo-watermark"'); expect(h).toContain('data-synthetic="true"');
    expect(h).toContain('This banner cannot be hidden');
    const banner = h.slice(h.indexOf('teoo-synthetic-banner'), h.indexOf('teoo-concept-notice'));
    expect(banner).not.toContain('<button'); expect(banner).not.toContain('onClick'); expect(banner).not.toContain('display:none');
  });
  it('derives the requirement from the data: a SYNTHETIC ancestor is enough, and a MEASURED-only dataset has none', () => {
    expect(needsSyntheticBanner(demo.records)).toBe(true);
    expect(needsSyntheticBanner([{ ...measured.record, provenance: 'RECONSTRUCTED_ESTIMATE', lineage_classes: ['MEASURED', 'SYNTHETIC', 'RECONSTRUCTED_ESTIMATE'] } as TeooRecord])).toBe(true);
    expect(needsSyntheticBanner([measured.record])).toBe(false);
    const m = html(measured.body, measured.coverage, [measured.record]);
    expect(m).not.toContain('teoo-synthetic-banner'); expect(m).not.toContain('teoo-watermark'); expect(m).toContain('data-synthetic="false"');
  });
  it('always says that the drawing is conceptual, not a photograph and not a measurement', () => {
    for (const x of [h, html(measured.body, measured.coverage, [measured.record]), html(demo.body, null, [])]) { expect(x).toContain('data-testid="teoo-concept-notice"'); expect(x).toContain('not a photograph'); }
    expect(CONCEPT_NOTICE).toContain('not an anatomical measurement');
  });
});

describe('View A: what is drawn is what the backend reports', () => {
  it('colours a part only by the provenance class of the records that refer to it', () => {
    const marks = marksOf(demo.body, demo.coverage);
    for (const m of marks.filter((x) => x.shape !== 'link')) expect(m.cls).toBe(demo.coverage.by_ref[m.ref] ?? 'unmeasured');
    const cls = (ref: string) => marks.find((m) => m.id === `j:${ref}`)?.cls;
    expect(cls('knee_l')).toBe('synthetic'); expect(cls('elbow_r')).toBe('limited'); expect(cls('ankle_l')).toBe('limited'); expect(cls('knee_r')).toBe('unmeasured');
    expect(marks.find((m) => m.id === 'n:thigh_l')?.cls).toBe('unmeasured');  // a target with no record is not drawn as measured, and not as absent
    const mm = marksOf(measured.body, measured.coverage);
    expect(mm.find((m) => m.id === 'j:knee_l')?.cls).toBe('measured'); expect(mm.filter((m) => m.cls === 'measured').length).toBe(2);
  });
  it('draws one mark per component, and a link and a joint marker per relation', () => {
    const v = demo.body.versions[demo.body.versions.length - 1];
    const marks = marksOf(demo.body, demo.coverage);
    expect(marks.filter((m) => m.shape === 'node').length).toBe(v.components.length);
    expect(marks.filter((m) => m.shape === 'link').length).toBe(v.relations.length); expect(marks.filter((m) => m.shape === 'joint').length).toBe(v.relations.length);
  });
  it('cites only records that exist, and only parts of the body that exist (the data and the drawing reference each other)', () => {
    const ids = new Set(demo.records.map((r) => r.record_id)), v = demo.body.versions[demo.body.versions.length - 1];
    const parts = new Set([...v.components.map((c) => c.id), ...v.relations.map((r) => r.id)]);
    for (const t of Object.values(demo.coverage.targets)) { expect(t.records.every((r) => ids.has(r))).toBe(true); expect(parts.has(t.ref)).toBe(true); }
    const h = html(demo.body, demo.coverage, demo.records, 'knee_l');
    expect(h).toContain('data-testid="teoo-detail"'); expect(h).toContain('data-ref="knee_l"');
    for (const r of targetsOfRef(demo.coverage, 'knee_l').flatMap((t) => t.records)) expect(h).toContain(r);
    for (const m of h.match(/data-ref="([^"]+)"/g) ?? []) expect(parts.has(m.slice(10, -1))).toBe(true);
  });
  it('shows the observation limits and the missing samples of a selected part, never a value', () => {
    const t = targetsOfRef(demo.coverage, 'elbow_r')[0], lines = describeTarget(t).join('\n');
    expect(lines).toContain('BOUNDARY_INVISIBLE'); expect(lines).toContain('observation limits: BOUNDARY_INVISIBLE'); expect(lines).not.toMatch(/value/i);
    const knee = describeTarget(targetsOfRef(demo.coverage, 'knee_l')[0]).join('\n');
    expect(knee).toContain('MISSING 40'); expect(knee).toContain('provenance: SYNTHETIC'); expect(knee).toContain('unsynchronised');
  });
  it('says that a part without a record is not observed, which is not the same as absent, and that an undeclared part has no variable', () => {
    const h = html(demo.body, demo.coverage, demo.records, 'thigh_l');
    expect(h).toContain('not the same as absent');
    expect(html(demo.body, demo.coverage, demo.records, 'forearm_l')).toContain('No observation target is declared for this part');
    expect(Object.values(CLASS_STYLE).every((s) => s.legend.length > 10)).toBe(true);
  });
  it('differs by more than colour: every class has its own outline or pattern', () => {
    const keys = new Set(Object.values(CLASS_STYLE).map((s) => `${s.dash}|${s.pattern}|${s.stroke}`));
    expect(keys.size).toBe(Object.keys(CLASS_STYLE).length);
  });
});

describe('View A: the human skeleton is a preset, not the schema', () => {
  it('draws a body without a concept layout on a circle, with the same code', () => {
    const rad = measured.radial, v = rad.versions[rad.versions.length - 1], L = layoutOf(v);
    expect(rad.family).toBe('non-human'); expect(L.kind).toBe('circle'); expect(Object.keys(L.pos).length).toBe(v.components.length);
    expect(Object.values(L.pos).every(([x, y]) => x >= 0 && x <= 200 && y >= 0 && y <= 200)).toBe(true);
    const h = html(rad, null, []);
    expect(h).toContain('generic circular layout'); expect((h.match(/data-class="unmeasured" data-testid="teoo-mark-/g) ?? []).length).toBe(v.components.length + v.relations.length);  // nothing observed: nothing coloured
    expect(layoutOf(demo.body.versions[0]).kind).toBe('concept');
  });
});

describe('the view is part of the application', () => {
  it('is addressed by ?view=body and has its own name', () => {
    expect(viewFromSearch('?view=body', ['network', 'body'], 'network')).toBe('body'); expect(searchForView('', 'body', 'network')).toBe('?view=body');
    expect(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'i18n', 'strings.ts'), 'utf8')).toContain("view_body: 'BODY / TOTAL OBSERVATION'");
  });
  it('is registered in the application and left out of the builds that have no backend', () => {
    const app = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'App.tsx'), 'utf8');
    expect(app).toContain("{ id: 'body'"); expect(app).toContain("view === 'body' && <BodyView />"); expect(app).toContain("!(v === 'body' && (NATIVE || WEBRT))");
    const statics = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'static-views.json'), 'utf8')) as string[];
    expect(statics).not.toContain('body');  // the public read-only mirror has no body data and no local backend
  });
});
