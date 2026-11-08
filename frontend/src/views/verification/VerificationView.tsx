import { useEffect, useState } from 'react';

// Verification — the Brassier Machine as an evidence ledger (backend/xzr/verification). It shows, for each claim of a SYNTHETIC demonstration, the verdict
// (SUPPORTED / WITHHELD / WITHDRAWN), the checks behind it, the evidence including negative results, and the ordinary AIC/BIC comparison beside it.
// It has no authority over what is real and says so on the page; nothing is computed here.

export type Check = Record<string, unknown> & { result?: string };
export interface EvidenceItem { id: string; outcome: string; source: string; protocol: { name?: string; interventions?: string[]; window?: number } | null; seeds: number[]; provenance: string; note: string }
export interface Entry { claim: string; text: string; verdict: string; authority: string; checks: Record<string, Check>; identification: { result: string; identified_by: string | null; equivalent_pairs_under_base: string[]; tolerance: number } | null; evidence: EvidenceItem[]; digest: string }
export interface Demo { brassier: { engine: string; enabled: boolean; authority: string; ledger: Entry[]; digest: string }; standard_comparison_clamp_vs_free_passive: { criterion: string; models: Record<string, { AIC: number; BIC: number; rss: number; k: number }>; preferred_by_AIC: string }; note: string; seal_intact: boolean }

const COLOUR: Record<string, string> = { SUPPORTED: '#3f9a63', WITHHELD: '#c79a2c', WITHDRAWN: '#c0564f' };
const WORDS: Record<string, string> = { SUPPORTED: 'supported by the evidence below', WITHHELD: 'held back: the evidence does not settle it', WITHDRAWN: 'withdrawn: the world evidence contradicts it' };

export function ClaimCard({ e }: { e: Entry }) {
  return (
    <article data-testid="verification-claim" style={{ border: '1px solid var(--line, #3a3a3a)', padding: 12, display: 'grid', gap: 8 }}>
      <header style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'baseline' }}>
        <span style={{ background: COLOUR[e.verdict] ?? '#777', color: '#fff', padding: '2px 8px', fontWeight: 600 }}>{e.verdict}</span>
        <span className="small dim">{WORDS[e.verdict] ?? ''}</span>
      </header>
      <p style={{ margin: 0 }}>{e.text}</p>
      <div style={{ overflowX: 'auto' }}>
        <table className="small">
          <tbody>
            {Object.entries(e.checks).map(([k, v]) => (
              <tr key={k}><th>{k.replace('_', ' ')}</th><td>{v.result ?? (Array.isArray(v.reasons) && v.reasons.length ? `reasons: ${(v.reasons as string[]).join('; ')}` : 'no reasons recorded')}</td></tr>
            ))}
            {e.identification && <tr><th>identification</th><td>{e.identification.result}{e.identification.identified_by ? ` by ${e.identification.identified_by}` : ''}{e.identification.equivalent_pairs_under_base.length ? ` (equivalent under passive observation: ${e.identification.equivalent_pairs_under_base.join(', ')})` : ''}</td></tr>}
          </tbody>
        </table>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="small">
          <caption>Evidence (negative results are kept)</caption>
          <thead><tr><th>id</th><th>outcome</th><th>source</th><th>protocol</th><th>seeds</th><th>provenance</th></tr></thead>
          <tbody>
            {e.evidence.map((x) => (
              <tr key={x.id}><td>{x.id}</td><td>{x.outcome}</td><td>{x.source}</td><td>{x.protocol?.name ?? '—'}{x.protocol?.interventions?.length ? ` [${x.protocol.interventions.join(', ')}]` : ''}</td><td>{x.seeds.join(', ')}</td><td>{x.provenance}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small dim" style={{ margin: 0 }}>digest {e.digest.slice(0, 16)}…</p>
    </article>
  );
}

export function StandardComparison({ d }: { d: Demo }) {
  const s = d.standard_comparison_clamp_vs_free_passive;
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="small" data-testid="verification-standard">
        <caption>The ordinary comparison on the same passive observations ({s.criterion}; lower is better)</caption>
        <thead><tr><th>model</th><th>parameters</th><th>residual sum of squares</th><th>AIC</th><th>BIC</th></tr></thead>
        <tbody>{Object.entries(s.models).map(([m, v]) => <tr key={m}><td>{m}</td><td>{v.k}</td><td>{v.rss.toExponential(2)}</td><td>{v.AIC.toFixed(2)}</td><td>{v.BIC.toFixed(2)}</td></tr>)}</tbody>
      </table>
      <p className="small dim">Both models predict the passive record equally well; the criteria differ only by the parameter count. The ledger records the equivalence and the intervention that separates the mechanisms.</p>
    </div>
  );
}

export function Boundary({ d }: { d: Demo }) {
  return (
    <div className="small" data-testid="verification-boundary">
      <p><b>Authority: none.</b> {d.brassier.authority}. A verdict is a statement about the evidence on file, never about what is real.</p>
      <p>{d.note}</p>
      <p>Seal of the record: {d.seal_intact ? 'intact (every digest matches its content)' : 'BROKEN (a digest does not match)'}; record digest {d.brassier.digest.slice(0, 16)}…</p>
      <p className="dim">Not done: the earlier Brassier Machine work (R35, R37) is not in this repository, so the mapping of these seven checks onto its six filters and its S/W division is not verified; no claim is made that the machine improves on standard methods.</p>
    </div>
  );
}

export default function VerificationView() {
  const [d, setD] = useState<Demo | null>(null), [err, setErr] = useState('');
  useEffect(() => { fetch('/api/verification/brassier/demo').then((r) => { if (!r.ok) throw new Error(`${r.status}`); return r.json() as Promise<Demo>; }).then(setD).catch((e: Error) => setErr(e.message)); }, []);
  if (err) return <section className="panel"><h2>Verification</h2><p role="alert">{err}. The Verification view needs the local runtime.</p></section>;
  if (!d) return <section className="panel"><h2>Verification</h2><p className="dim">loading the ledger…</p></section>;
  return (
    <section className="panel" aria-labelledby="ver-h" style={{ padding: 16, display: 'grid', gap: 16 }}>
      <header>
        <h2 id="ver-h">Verification — the Brassier Machine</h2>
        <p className="small dim">An evidence ledger for ontological claims: what stands behind each claim, what would withdraw it, and whether competing mechanisms can be told apart. SYNTHETIC demonstration worlds.</p>
      </header>
      {d.brassier.ledger.map((e) => <ClaimCard key={e.claim} e={e} />)}
      <StandardComparison d={d} />
      <Boundary d={d} />
    </section>
  );
}
