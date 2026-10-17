// Guards the user-facing wording that states what XENO ZIRAN SIMULATOR is and what its public deployment shows:
// prediction is scoped to the published result views (never denied for the simulator as a whole), the Philosophical
// Runtime is one operational region (not the end of the hierarchy), and a null measurement is not read as absence.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (p: string) => readFileSync(join(root, p), 'utf8');

const USER_FACING = [
  'frontend/index.html', 'frontend/src/i18n/strings.ts', 'frontend/src/App.tsx',
  'frontend/src/components/Orientation.tsx', 'frontend/src/components/ShareStrip.tsx',
  'README.md', 'docs/ARCHITECTURE.md', 'docs/LIMITATIONS.md', 'backend/xzr/__init__.py',
];
const flat = (s: string) => s.replace(/\s+/g, ' ');
const orientation = read('frontend/src/components/Orientation.tsx');
const shell = read('frontend/index.html');

describe('prediction is scoped to the published result views', () => {
  it('no user-facing text denies prediction for the simulator as a whole', () => {
    const denial = /\bnot (a |an )?predict(ive|ion)\b|non-?predictive|prediction engine|予測ではありません/i;
    for (const p of USER_FACING) expect([p, denial.test(read(p))]).toEqual([p, false]);
  });

  it('the deployment-scoped statement is present where the public site is described', () => {
    const scoped = 'published result views are experimental and analytical outputs and should not be interpreted as real-world forecasts or predictive claims';
    expect(flat(orientation)).toContain(scoped);
    expect(flat(shell)).toContain(scoped);
    expect(read('frontend/src/i18n/strings.ts')).toMatch(/footer_static: 'This public deployment presents experimental results; it does not make real-world predictive claims\.'/);
  });
});

describe('the Philosophical Runtime is one operational region', () => {
  it('is never the last link of the hierarchy chain', () => {
    for (const p of ['frontend/src/components/Orientation.tsx', 'frontend/index.html', 'README.md']) {
      expect([p, /›[^›.<]*Philosophical Runtime/.test(read(p))]).toEqual([p, false]);
    }
  });

  it('sits beside the experimental runtime and the research results', () => {
    for (const region of ['Experimental runtime', 'Research results', 'Philosophical Runtime']) expect(orientation).toContain(region);
  });
});

describe('a null measurement is not read as absence', () => {
  it('keeps the distinctions of the measurement interpretation', () => {
    const text = orientation.replace(/\s+/g, ' ');
    for (const s of ['"not detected" means no difference above the stated noise floor', 'not that none exists',
      'not measured', 'measurement apparatus, scale or time window', 'inaccessible to the observation used',
      'no difference was detected within the represented and measured state under the stated comparison procedure',
      'equivalence within a stated margin is reported as such',
      'Neither is a claim of genuine absence, which would need independent justification']) expect(text).toContain(s);
  });

  it('bit identity is never re-described as absence anywhere user-facing or in the research docs', () => {
    const files = [...USER_FACING, 'frontend/src/views/resolution/HiddenDifferenceView.tsx',
      'frontend/src/views/resolution/ReasoningStructureView.tsx', 'frontend/src/views/resolution/ResolutionMatrixView.tsx',
      'frontend/src/views/resolution/DisconnectionView.tsx', 'docs/RESOLUTION_ESCALATION.md', 'docs/REASONING_CONFIGURATION_MAP.md',
      'docs/DISCONNECTION.md', 'docs/REDUCTION.md', 'docs/EXPERIMENT_RESULTS.md', 'backend/scripts/escalation_reports.py'];
    const claims = [
      /bit-identical[^.|]{0,80}\b(proves?|proof of|establish(es)?) (the )?(absence|nonexistence)/i,  // bit identity as proof
      /absence of difference is stated[^.]{0,40}bit-identical/i,  // the earlier wording
      /only bit-identical runs are redundant/i,
      /\babsent at\b/i, /\babsent \(equivalent\)/i, /\bwhere it is absent\b/i, /genuinely redundant/i,
      /no difference (really )?exists/i,
    ];
    for (const p of files) {
      const text = flat(read(p));
      for (const c of claims) expect([p, c.source, c.test(text)]).toEqual([p, c.source, false]);
    }
  });

  it('the redundancy label is defined as a measurement-bounded operational label', () => {
    const doc = flat(read('docs/RESOLUTION_ESCALATION.md'));
    expect(doc).toContain('This is an operational label: no difference was detected within the represented and measured state under the stated comparison procedure. It is not a claim of genuine absence');
    expect(flat(read('docs/REDUCTION.md'))).toContain('"Bit-identical" means no difference was detected within the represented and measured state');
  });
});

describe('identity', () => {
  it('the application is XENO ZIRAN SIMULATOR and the public site is described as part of it', () => {
    expect(read('frontend/src/i18n/strings.ts')).toMatch(/title: 'XENO ZIRAN SIMULATOR'/);
    expect(shell).toMatch(/<title>XENO ZIRAN SIMULATOR<\/title>/);
    // the public site states what each part is: result views read-only, the simulator in the browser at /app/
    const text = orientation.replace(/\s+/g, ' ');
    expect(text).toContain('The research-result views on this page are read-only: no simulation runs here');
    expect(text).toContain('The simulator runs in your browser tab at <a href="/app/">/app/</a>');
  });
});
