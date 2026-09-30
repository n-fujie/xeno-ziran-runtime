import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useSim } from '../store/sim';
import { t } from '../i18n/strings';

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
  const [samples, setSamples] = useState<{ id: string; name: string }[]>([]);
  const [speed, setSpeed] = useState(20);

  useEffect(() => { void api.scenarios().then(setSamples); }, []);
  if (!info || !status) return <div className="controlbar" />;
  const running = status.running;
  const cps = status.checkpoints ?? [];

  return (
    <div className="controlbar">
      <div className="group">
        <button className={running ? 'on' : ''} onClick={() => void control(running ? 'pause' : 'run', { speed })}
          title={t('run_pause')}>{running ? '❚❚ ' + t('pause') : '▶ ' + t('run')}</button>
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
        <span className="mono num">{speed > 120 ? 'max' : `${speed}/s`}</span>
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
          {samples.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <button onClick={async () => {
          const saved = await api.save(info.id);
          const blob = new Blob([JSON.stringify(saved, null, 2)], { type: 'application/json' });
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
