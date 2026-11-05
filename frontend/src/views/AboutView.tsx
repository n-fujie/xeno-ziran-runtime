// About (iOS app only): what runs in this app, under which limits, and where the other editions of the simulator are.
// The limits are read from the running in-process runtime, not written here; the rest states what the code of this app
// contains (the same interactive views, the engine staged by ios/scripts/stage_engine.py) and what it does not.
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { nativeOpenResults } from '../api/native';

type Limits = NonNullable<Awaited<ReturnType<typeof api.health>>['limits']>;

export default function AboutView() {
  const [limits, setLimits] = useState<Limits | null>(null);
  const [version, setVersion] = useState<string | null>(null);
  useEffect(() => { void api.health().then((h) => { setLimits(h.limits ?? null); setVersion(h.version ?? null); }).catch(() => {}); }, []);
  const n = (v: number) => v.toLocaleString();
  return (
    <div className="panel-view about">
      <h2>On this device</h2>
      <p>The simulator runs in this app, on your iPhone or iPad. The engine is the same Python source as the desktop
        runtime{version ? ` (engine ${version})` : ''}, embedded in the app. No server, account or network connection is used to
        simulate; nothing you load or export leaves the device unless you share it yourself.</p>
      <p className="small dim">Views here: Network, Shape Space, Address Space, World Map, 3D Globe, Timeline, Compare and
        Philosophical Practice. A running simulation is paused when the app leaves the foreground.</p>

      <h3>Limits of this runtime</h3>
      {limits ? (
        <ul className="small">
          <li>worlds of up to {n(limits.max_nodes)} configurations and {n(limits.max_edges)} connections (larger ones are refused with a message, never cut)</li>
          <li>up to {n(limits.max_sessions)} sessions at a time, {n(limits.max_checkpoints)} checkpoints to rewind to</li>
          <li>comparisons of up to {n(limits.max_compare_horizon)} steps</li>
          <li>exports up to {n(limits.max_export_bytes / 1_000_000)} MB</li>
        </ul>
      ) : <p className="small dim">reading the limits of this runtime…</p>}
      <p className="small dim">The address hierarchy of a world that is not one of the bundled scenarios is computed on the device
        with a different eigensolver, so address-based results may differ from the desktop runtime's (the footer says so when it applies).</p>

      <h3>What is not in this app</h3>
      <p className="small">The published research-result views, the 3D Laboratory and the research layers of the local
        full runtime are not part of the app. The research results are published on the research-results site, which opens
        in your browser:</p>
      <p><button className="external" onClick={nativeOpenResults}>Research Results ↗</button></p>

      <h3>Other editions — not equivalent to this app</h3>
      <ul className="small">
        <li><b>Browser Edition</b>: runs the simulator in a browser tab (Pyodide, WebAssembly) with smaller workloads; floating-point results can differ from the desktop runtime in the last digits.</li>
        <li><b>Research results (read-only)</b>: shows published experiment results; it does not run a simulation.</li>
        <li><b>Local full runtime</b>: the desktop runtime with a local backend, for large worlds and long experiment runs.</li>
      </ul>
      <p className="small dim">Features and data formats can differ between these editions. A session file saved here is the format
        the desktop runtime's Save and Load use.</p>
      <p className="small dim">The simulator is an experimental and analytical environment; its outputs are not real-world forecasts.</p>
    </div>
  );
}
