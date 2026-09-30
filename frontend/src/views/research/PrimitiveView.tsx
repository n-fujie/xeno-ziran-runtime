import { useEffect, useState } from 'react';
import { api, type PrimitiveEntry } from '../../api/client';
import { Status } from './common';

export default function PrimitiveView() {
  const [list, setList] = useState<PrimitiveEntry[] | null>(null);
  const [sel, setSel] = useState(0);
  useEffect(() => { void api.primitives().then(setList); }, []);
  if (!list) return <div className="panel-view dim">loading…</div>;
  const p = list[sel];
  return (
    <div className="primitives">
      <ul className="prim-list">
        {list.map((x, i) => (
          <li key={x.primitive} className={i === sel ? 'on' : ''} onClick={() => setSel(i)}>
            <span>{x.name}</span><Status s={x.status.split(' (')[0]} />
          </li>
        ))}
      </ul>
      <div className="prim-detail panel-view">
        <h3>{p.primitive}</h3>
        <p>{p.definition}</p>
        <table className="kv mono small"><tbody>
          <tr><td>status</td><td><Status s={p.status} /></td></tr>
          <tr><td>question</td><td>{p.question ?? '—'}</td></tr>
          <tr><td>rule applied</td><td>{p.rule ?? '—'}</td></tr>
          {p.reduced_to && <tr><td>reduced to</td><td>{p.reduced_to}</td></tr>}
          {p.diverges_in && <tr><td>removal diverges in</td><td>{p.diverges_in.join(', ') || 'no regime'}</td></tr>}
          {p.why_unresolved && <tr><td>why unresolved</td><td>{p.why_unresolved}</td></tr>}
          <tr><td>implementation</td><td>{p.implementation.map((x) => <div key={x}>{x}</div>)}</td></tr>
          <tr><td>runtime flags</td><td>{p.flags.join(', ') || '—'}</td></tr>
          <tr><td>dependent tests</td><td>{p.tests.map((x) => <div key={x}>{x}</div>)}</td></tr>
        </tbody></table>
        <h4>Experimental evidence</h4>
        <ul className="mono small evidence-list">{p.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
      </div>
    </div>
  );
}
