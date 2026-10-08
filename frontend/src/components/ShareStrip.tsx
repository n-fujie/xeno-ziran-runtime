// Actions of a research view: download the result file the view is generated from (unchanged, as served by
// /api/experiments/<name>) and copy the view's URL. Shown only for views that are backed by a result file.
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Listing } from '../api/results';
import type { View } from '../store/sim';

// view -> result file it reads (the API name; the file is <name>.json)
export const SOURCE_OF: Partial<Record<View, string>> = {
  reduction: 'reduction', reason: 'reason', phases: 'reason', primitives: 'primitives',
  res_matrix: 'resolution-summary', res_hidden: 'resolution-summary', res_penetration: 'resolution-summary',
  res_structure: 'resolution-summary', res_disconnection: 'resolution-summary', res_compression: 'resolution-summary',
};

const mb = (b: number) => (b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} kB`);

export default function ShareStrip({ view }: { view: View }) {
  const name = SOURCE_OF[view];
  const [meta, setMeta] = useState<Listing[number] | null>(null);
  const [copied, setCopied] = useState<string>('');
  useEffect(() => {
    setCopied('');
    if (!name) return;
    let alive = true;
    api.experiments().then((l) => { if (alive) setMeta(l.find((e) => e.name === name) ?? null); }).catch(() => {});
    return () => { alive = false; };
  }, [name, view]);
  if (!name) return null;
  const file = `${name}.json`;
  const copy = () => {
    const legacy = () => {  // where the Clipboard API is not permitted
      const ta = document.createElement('textarea');
      ta.value = location.href;
      ta.style.cssText = 'position:fixed;opacity:0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      ta.remove();
      setCopied(ok ? 'link copied' : 'copy unavailable: use the address bar URL');
    };
    if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(() => setCopied('link copied'), legacy);
    else legacy();
  };
  return (
    <div className="share-strip small" aria-label="result actions">
      <span className="dim">source data</span>
      <span className="mono">{file}</span>
      <span className="dim">
        application/json{meta && <> · {mb(meta.bytes)} · generated {new Date(meta.modified * 1000).toISOString().slice(0, 10)}</>}
        {name === 'primitives' && ' · generated from the runtime primitive catalog'}
        {meta?.sha256 && <> · sha256 <span className="mono" title={meta.sha256}>{meta.sha256.slice(0, 12)}…</span></>}
        {meta?.sections && ' · a view loads either this file or only the sections it renders (lossless split), whichever is smaller; the download is the complete original file'}
      </span>
      <a className="button" href={`/api/experiments/${name}`} download={`xeno-ziran-simulator_${file}`}
        type="application/json">Download JSON</a>
      <button onClick={copy}>Copy link to this view</button>
      <span className="status dim" role="status">{copied}</span>
    </div>
  );
}
