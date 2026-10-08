import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { NATIVE, nativeFetch, nativeShare } from '../api/native';
import { useSim } from '../store/sim';
import { t } from '../i18n/strings';

// the pause bars (U+275A) are not in the iOS system fonts the app uses offline (and U+23F8 renders as a missing
// glyph there too): the app's button is labelled by its word only
const PAUSE = NATIVE ? '' : '❚❚ ';

export default function ControlBar() {
  const info = useSim((s) => s.info);
  const status = useSim((s) => s.status);
  const stream = useSim((s) => s.stream);
  const fps = useSim((s) => s.fps);
  const connected = useSim((s) => s.connected);
  const control = useSim((s) => s.control);
  const rewind = useSim((s) => s.rewind);
  const open = useSim((s) => s.open);
  const openSaved = useSim((s) => s.openSaved);
  const [samples, setSamples] = useState<{ id: string; name: string; configurations: number }[]>([]);
  const [speed, setSpeed] = useState(20);

  useEffect(() => { void api.scenarios().then(setSamples); }, []);
  const [maxNodes, setMaxNodes] = useState<number | null>(null);
  useEffect(() => { void api.health().then((h) => setMaxNodes(h.max_nodes ?? null)).catch(() => {}); }, []);
  if (!info || !status) return <div className="controlbar" />;
  const running = status.running;
  const cps = status.checkpoints ?? [];

  return (
    <div className="controlbar">
      <div className="group">
        <button className={running ? 'on' : ''} onClick={() => void control(running ? 'pause' : 'run', { speed })}
          title={t('run_pause')}>{running ? PAUSE + t('pause') : '▶ ' + t('run')}</button>
        <button onClick={() => void control('step', { steps: 1 })} disabled={running}>{t('step')}</button>
        <button onClick={() => void control('step', { steps: 10 })} disabled={running}>+10</button>
        <button onClick={() => void control('reset')} title={t('reset_hint')}>{t('reset')}</button>
      </div>
      <div className="group">
        <label className="dim">{t('speed')}</label>
        <input type="range" min={1} max={121} value={speed}
          onChange={(e) => {
            const v = Number(e.target.value);
            setSpeed(v);
            void control('speed', { speed: v > 120 ? 0 : v });
          }} />
        <span className="mono num" title={status.speed_limit ? `this runtime allows at most ${status.speed_limit} steps/s` : undefined}>
          {status.speed_limit && (speed > 120 || speed > status.speed_limit) ? `${status.speed_limit}/s (limit)` : speed > 120 ? 'max' : `${speed}/s`}</span>
      </div>
      <div className="group">
        <label className="dim">{t('rewind')}</label>
        <select value="" onChange={(e) => { if (e.target.value) void rewind(Number(e.target.value)); }}>
          <option value="">{t('checkpoint')}…</option>
          {cps.map((c) => <option key={c} value={c}>t = {c}</option>)}
        </select>
      </div>
      <div className="group stats mono">
        <span title={t('step_counter')}>t {status.t.toLocaleString()}</span>
        <span title={t('sim_rate')}>{status.steps_per_second.toFixed(0)} steps/s</span>
        <span title={t('render_rate')}>{fps} fps</span>
        <span title={t('ws_rate')}>{stream.framesPerSec.toFixed(0)} upd/s · {(stream.bytesPerSec / 1024).toFixed(0)} KiB/s</span>
        <span title={t('connections')}>{status.connections.toLocaleString()} conn</span>
        <span className={connected ? 'ok' : 'warn'}>{connected ? '●' : '○'}</span>
      </div>
      <div className="group right">
        <select value="" onChange={(e) => { if (e.target.value) void open(e.target.value); }}>
          <option value="">{t('scenario')}: {info.scenario.name}</option>
          {samples.map((s) => {
            const over = maxNodes !== null && s.configurations > maxNodes;  // refused by this runtime's limit
            return <option key={s.id} value={s.id} disabled={over}>{s.name}{over ? ` — exceeds this runtime's limit of ${maxNodes.toLocaleString()} configurations` : ''}</option>;
          })}
        </select>
        <button onClick={async () => {
          const saved = await api.save(info.id);
          const text = JSON.stringify(saved, null, 2);
          // the same file as the desktop runtime's Save; on iOS it goes to the share sheet (Files, AirDrop, …)
          if (NATIVE) return void nativeShare(`xzr-session-t${status.t}.json`, 'application/json', text);
          const blob = new Blob([text], { type: 'application/json' });
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = `xzr-session-t${status.t}.json`;
          a.click();
        }}>{t('save')}</button>
        <label className="button">
          {t('load')}
          <input type="file" accept="application/json" hidden onChange={async (e) => {
            const f = e.target.files?.[0];
            if (f) void openSaved(JSON.parse(await f.text()));
          }} />
        </label>
        <ExportMenu sid={info.id} />
      </div>
    </div>
  );
}

function ExportMenu({ sid }: { sid: string }) {
  return (
    <select value="" onChange={(e) => {
      if (!e.target.value) return;
      const [what, format] = e.target.value.split(':');
      if (NATIVE) return void exportNative(sid, what, format);
      window.open(api.exportUrl(sid, what, format), '_blank');
    }}>
      <option value="">{t('export')}…</option>
      <option value="nodes:csv">configurations · CSV</option>
      <option value="edges:csv">connections · CSV</option>
      <option value="events:csv">event log · CSV</option>
      <option value="events:json">event log · JSON</option>
      <option value="metrics:csv">metrics · CSV</option>
      <option value="metrics:json">metrics · JSON</option>
      <option value="scenario:json">scenario + interventions · JSON</option>
    </select>
  );
}

async function exportNative(sid: string, what: string, format: string) {
  const r = await nativeFetch(api.exportUrl(sid, what, format));
  const text = await r.text();
  if (!r.ok) {
    useSim.setState({ error: `Export failed: ${text}` });
    return;
  }
  const json = format === 'json';
  await nativeShare(`xzr-${what}.${format}`, json ? 'application/json' : 'text/csv',
    json ? JSON.stringify(JSON.parse(text), null, 2) : text);
}
