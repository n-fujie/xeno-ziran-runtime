import { useState } from 'react';
import { C } from '../views/palette';

const rgb = (c: number[]) => `rgb(${c[0]},${c[1]},${c[2]})`;

const ITEMS: [string, string, string][] = [
  ['dot', rgb([255, 255, 255]), 'ignition — brief pulse'],
  ['dot', rgb([140, 140, 145]), 'retention — brightness ∝ difference / threshold'],
  ['ring', rgb([200, 200, 210]), 'memory — decaying afterimage ring'],
  ['dot', rgb(C.penetration), 'penetration — difference travelling along a connection'],
  ['ring', rgb(C.ret), 'return — a wave came back to its origin'],
  ['ring', rgb([255, 255, 255]), 'branching — one ignition caused several'],
  ['line', rgb(C.cut), 'cut — connection breaks'],
  ['line', rgb(C.newConn), 'new connection'],
  ['line', rgb(C.reconf), 'reconfiguration — connection redirected'],
  ['line', rgb(C.gated), 'boundary — reduced permeability'],
  ['dot', rgb(C.frozen), 'frozen configuration (local constraint)'],
];

export default function Legend() {
  const [open, setOpen] = useState(false);
  return (
    <div className={`legend ${open ? 'open' : ''}`}>
      <button className="ghost small" onClick={() => setOpen(!open)}>{open ? 'hide legend' : 'legend'}</button>
      {open && (
        <ul>
          {ITEMS.map(([kind, color, label]) => (
            <li key={label}><i className={kind} style={{ [kind === 'line' ? 'background' : kind === 'ring' ? 'borderColor' : 'background']: color }} />{label}</li>
          ))}
          <li className="dim small">Hue is used only for operational distinctions.</li>
        </ul>
      )}
    </div>
  );
}
