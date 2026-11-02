import { useEffect, useMemo, useState } from 'react';
import './body.css';
import { teooBodyPreset, teooCoverage, teooDemo, type Coverage, type DemoResponse, type TeooBody, type TeooRecord } from './bodyApi';
import { CLASS_ORDER, CLASS_STYLE, describeTarget, layoutOf, marksOf, needsSyntheticBanner, targetsOfRef, type Mark } from './bodyDraw';

// BODY / TOTAL OBSERVATION — View A: Body Observation. A simplified drawing of a declared body; each part is coloured by the provenance class of the records that
// refer to it, and by nothing else. It is a conceptual illustration: not a photograph, not an anatomical measurement. SYNTHETIC data always carry a banner and a
// watermark that no control can remove.

export const CONCEPT_NOTICE = 'CONCEPTUAL ILLUSTRATION — a simplified drawing of a declared body, not a photograph and not an anatomical measurement. Colour shows which parts have records, nothing else.';

export interface BodyObservationProps { body: TeooBody; coverage: Coverage | null; records: TeooRecord[]; selected: string | null; onSelect: (ref: string | null) => void }

const patternId = (cls: string) => `teoo-pat-${cls}`;

function Marks({ marks, selected, onSelect }: { marks: Mark[]; selected: string | null; onSelect: (r: string | null) => void }) {
  return (
    <>
      {marks.filter((m) => m.shape === 'link').map((m) => <line key={m.id} x1={m.x} y1={m.y} x2={m.x2} y2={m.y2} stroke={m.severed ? '#ff8a70' : '#3a3a42'} strokeWidth={m.severed ? 1 : 1.6} strokeDasharray={m.severed ? '2 2' : undefined} />)}
      {marks.filter((m) => m.shape !== 'link').map((m) => {
        const st = CLASS_STYLE[m.cls], r = m.shape === 'joint' ? 2.6 : 4.2, on = selected === m.ref;
        return (
          <g key={m.id} role="button" tabIndex={0} aria-label={`${m.label}: ${st.label}`} data-ref={m.ref} data-class={m.cls} data-testid={`teoo-mark-${m.id}`} className={`teoo-mark${on ? ' on' : ''}`}
            onClick={() => onSelect(on ? null : m.ref)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(on ? null : m.ref); } }}>
            <circle cx={m.x} cy={m.y} r={r} fill={st.pattern === 'none' ? st.fill : `url(#${patternId(m.cls)})`} stroke={on ? '#fff' : st.stroke} strokeWidth={on ? 1.4 : 0.9} strokeDasharray={st.dash || undefined} />
            <title>{`${m.label} — ${st.label}`}</title>
          </g>
        );
      })}
    </>
  );
}

export function BodyObservation({ body, coverage, records, selected, onSelect }: BodyObservationProps) {
  const v = body.versions[body.versions.length - 1];
  const L = useMemo(() => layoutOf(v), [v]), marks = useMemo(() => marksOf(body, coverage), [body, coverage]);
  const banner = needsSyntheticBanner(records);
  const sel = selected ? targetsOfRef(coverage, selected) : [];
  return (
    <div className="teoo" data-synthetic={banner ? 'true' : 'false'} data-testid="teoo-view-a">
      {banner && <div className="teoo-banner" role="alert" data-testid="teoo-synthetic-banner">SYNTHETIC — artificial functional-test data. Not a measurement, not a physiological model. This banner cannot be hidden.</div>}
      <div className="teoo-note" data-testid="teoo-concept-notice">{CONCEPT_NOTICE}</div>
      <div className="teoo-main">
        <figure className={`teoo-figure${banner ? ' synthetic' : ''}`}>
          <svg viewBox={L.viewBox} role="img" aria-label={`Conceptual drawing of the body preset ${body.meta.preset ?? body.id}, version ${v.version}`} data-testid="teoo-svg">
            <defs>
              <pattern id={patternId('unmeasured')} width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="3" height="3" fill={CLASS_STYLE.unmeasured.fill} /><line x1="0" y1="0" x2="0" y2="3" stroke="#3a3a42" strokeWidth="0.8" /></pattern>
              <pattern id={patternId('limited')} width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)"><rect width="3" height="3" fill={CLASS_STYLE.limited.fill} /><line x1="0" y1="0" x2="0" y2="3" stroke="#ff8a70" strokeWidth="0.6" /></pattern>
              <pattern id={patternId('synthetic')} width="3" height="3" patternUnits="userSpaceOnUse"><rect width="3" height="3" fill={CLASS_STYLE.synthetic.fill} /><line x1="0" y1="1.5" x2="3" y2="1.5" stroke="#9bb0d0" strokeWidth="0.7" /></pattern>
              <pattern id={patternId('estimated')} width="3" height="3" patternUnits="userSpaceOnUse"><rect width="3" height="3" fill={CLASS_STYLE.estimated.fill} /><circle cx="1.5" cy="1.5" r="0.5" fill="#c9a227" /></pattern>
            </defs>
            <Marks marks={marks} selected={selected} onSelect={onSelect} />
          </svg>
          {banner && <div className="teoo-watermark" aria-hidden="true" data-testid="teoo-watermark">SYNTHETIC</div>}
          <figcaption className="small dim">{body.name} · family {body.family} · version {v.version} · {L.kind === 'concept' ? 'concept layout (a drawing)' : 'generic circular layout (no concept drawing for this body)'}</figcaption>
        </figure>
        <aside className="teoo-side">
          <h4>Legend</h4>
          <ul className="teoo-legend" data-testid="teoo-legend">
            {CLASS_ORDER.map((c) => <li key={c} data-class={c}><svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" fill={CLASS_STYLE[c].pattern === 'none' ? CLASS_STYLE[c].fill : `url(#${patternId(c)})`} stroke={CLASS_STYLE[c].stroke} strokeDasharray={CLASS_STYLE[c].dash || undefined} /></svg> <b>{CLASS_STYLE[c].label}</b> <span className="dim small">{CLASS_STYLE[c].legend}</span></li>)}
          </ul>
          <h4>Selected part</h4>
          {selected ? (
            <div data-testid="teoo-detail" data-ref={selected}>
              <div className="mono">{selected}</div>
              {sel.length === 0 && <div className="dim small">No observation target is declared for this part: no variable is registered for it, so nothing can have been observed there.</div>}
              {sel.map((t) => <div key={t.target} className="teoo-target" data-target={t.target}><div className="mono small">{t.target} · {t.variables.join(', ') || 'no variable'}</div><ul>{describeTarget(t).map((l, i) => <li key={i} className="small">{l}</li>)}</ul></div>)}
            </div>
          ) : <div className="dim small">Select a part of the drawing.</div>}
        </aside>
      </div>
    </div>
  );
}

export default function BodyView() {
  const [demo, setDemo] = useState<DemoResponse | null>(null);
  const [preset, setPreset] = useState('human-simplified-skeleton');
  const [alt, setAlt] = useState<{ body: TeooBody; coverage: Coverage } | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { teooDemo().then(setDemo).catch((e: Error) => setErr(e.message)); }, []);
  useEffect(() => {
    if (!demo || preset === 'human-simplified-skeleton') { setAlt(null); return; }
    teooBodyPreset(preset).then(async (b) => setAlt({ body: b.body, coverage: await teooCoverage(demo.records, preset) })).catch((e: Error) => setErr(e.message));
  }, [preset, demo]);
  if (err) return <div className="panel-view" data-testid="teoo-error"><b>BODY / TOTAL OBSERVATION</b><div className="dim">{err}</div></div>;
  if (!demo) return <div className="panel-view dim">loading…</div>;
  const body = alt?.body ?? demo.body, coverage = alt?.coverage ?? demo.coverage;
  return (
    <div className="panel-view teoo-root" data-testid="teoo-root">
      <header className="teoo-head"><h3>BODY / TOTAL OBSERVATION</h3><span className="dim small">View A — Body Observation · TEOO {demo.info.version}</span></header>
      <div className="teoo-controls"><label>body preset <select value={preset} onChange={(e) => { setPreset(e.target.value); setSelected(null); }} data-testid="teoo-preset">{demo.info.presets.map((p) => <option key={p}>{p}</option>)}</select></label>
        <span className="dim small">The human skeleton is one preset among others; a body is a declared graph.</span></div>
      <BodyObservation body={body} coverage={coverage} records={demo.records} selected={selected} onSelect={setSelected} />
      <section className="teoo-records" data-testid="teoo-records">
        <h4>Records loaded</h4>
        <table className="small"><thead><tr><th>record</th><th>provenance</th><th>kind</th><th>label</th><th>cited by this drawing</th><th>raw digest</th></tr></thead>
          <tbody>{demo.records.map((r) => { const ev = demo.evidence.find((e) => e.record_id === r.record_id); const n = Object.values(coverage.targets).filter((t) => t.records.includes(r.record_id)).length;
            return <tr key={r.record_id} data-testid="teoo-record-row"><td className="mono">{r.record_id}</td><td>{r.provenance}</td><td>{r.kind}</td><td>{ev?.label}</td><td>{n ? `${n} target(s)` : 'no: none of this body\'s targets refers to it'}</td><td className="mono">{r.raw.digest.slice(0, 12)}…</td></tr>; })}</tbody></table>
        <div className="dim small">Ledger: {demo.ledger.entries} entr{demo.ledger.entries === 1 ? 'y' : 'ies'}, {demo.ledger.issues.length === 0 ? 'verified' : `${demo.ledger.issues.length} issue(s)`}. Nothing is stored on the server. Digests detect a change; they do not authenticate a record.</div>
      </section>
      <section className="teoo-protections" data-testid="teoo-protections">
        <h4>Protections</h4>
        <div className="small"><b>Not implemented:</b> {demo.info.protections.not_implemented.join('; ')}.</div>
      </section>
    </div>
  );
}
