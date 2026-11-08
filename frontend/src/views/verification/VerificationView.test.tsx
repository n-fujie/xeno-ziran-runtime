// Verification view: the panels render the ledger as served by the backend and carry the "no authority" wording and the negative results.
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { Boundary, ClaimCard, StandardComparison, type Demo, type Entry } from './VerificationView';

const entry = (verdict: string): Entry => ({
  claim: 'c', text: 'a claim', verdict, authority: 'none: this record is an evidence ledger', digest: 'a'.repeat(64),
  checks: { independence: { result: 'INDEPENDENT_EVIDENCE' }, withdrawal: { reasons: ['world evidence contradicts the claim'] } },
  identification: { result: 'IDENTIFIED', identified_by: 'clamp intervention', equivalent_pairs_under_base: ['M1|M2'], tolerance: 1e-6 },
  evidence: [{ id: 'e-neg', outcome: 'contradicts', source: 'observation', protocol: { name: 'passive observation', interventions: [] }, seeds: [0], provenance: 'demo', note: '' }],
});
const demo: Demo = {
  brassier: { engine: 'brassier/1', enabled: true, authority: 'none: this record is an evidence ledger, not a determination of what is real', ledger: [entry('WITHDRAWN')], digest: 'b'.repeat(64) },
  standard_comparison_clamp_vs_free_passive: { criterion: 'Gaussian AIC / BIC', models: { M1: { AIC: 1, BIC: 2, rss: 0, k: 1 }, M2: { AIC: 3, BIC: 5, rss: 0, k: 2 } }, preferred_by_AIC: 'M1' },
  note: 'SYNTHETIC demonstration', seal_intact: true,
};
const txt = (h: string) => h.replace(/<!-- -->/g, '').replace(/&#x27;/g, "'");

describe('Verification panels', () => {
  it('shows the verdict, the identification, and keeps the negative result in the evidence table', () => {
    const h = txt(renderToString(<ClaimCard e={entry('WITHDRAWN')} />));
    expect(h).toContain('WITHDRAWN');
    expect(h).toContain('IDENTIFIED by clamp intervention');
    expect(h).toContain('e-neg');
    expect(h).toContain('contradicts');
    expect(h).toContain('reasons: world evidence contradicts the claim');
  });
  it('states that the machine has no authority and what was not done', () => {
    const h = txt(renderToString(<Boundary d={demo} />));
    expect(h).toContain('Authority: none.');
    expect(h).toContain('never about what is real');
    expect(h).toContain('not verified');
    expect(h).toContain('intact');
  });
  it('shows the standard comparison beside the ledger and says it ties on the data', () => {
    const h = txt(renderToString(<StandardComparison d={demo} />));
    expect(h).toContain('Gaussian AIC / BIC');
    expect(h).toContain('differ only by the parameter count');
  });
});
