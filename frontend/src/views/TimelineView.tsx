import { useEffect, useMemo, useState } from 'react';
import { api, type Metrics } from '../api/client';
import Chart, { type Marker } from '../components/Chart';
import { useSim } from '../store/sim';

const STEP_GROUPS: { title: string; keys: string[] }[] = [
  { title: 'ignition · penetration', keys: ['ignitions', 'penetrations'] },
  { title: 'returns · re-ignition · branch points', keys: ['returns', 'reignitions', 'branch_points'] },
  { title: 'amplification ratio · branching ratio', keys: ['amplification', 'branching'] },
  { title: 'topology change (cuts + new + removed + reconfigured)', keys: ['topology_change'] },
  { title: 'concentration · persistence · memory dependence · recurrence', keys: ['concentration', 'persistence', 'memory_dependence', 'recurrence'] },
];
const GRAPH_GROUPS: { title: string; keys: string[] }[] = [
  { title: 'reachability (dynamic · 2-hop · closure)', keys: ['reach_dynamic', 'reach_horizon', 'reach_closure'] },
  { title: 'closure: loop fraction · fragmentation', keys: ['loop_fraction', 'fragmentation'] },
  { title: 'bottleneck concentration · asymmetry · one-way share', keys: ['bottleneck_concentration', 'asymmetry', 'one_way_share'] },
  { title: 'difference concentration · path dependency', keys: ['difference_concentration', 'path_dependency'] },
  { title: 'connections', keys: ['connections'] },
];
const SHADES = ['#e6e6ea', '#8f8f96', '#5a5a61', '#b4b4ba'];
const EVENT_COLORS: Record<string, string> = {
  sudden_topology_change: '#ff5c48', loop_formation: '#ffbe5a', loop_dissolution: '#966ee0', fragmentation: '#ff5c48',
  recurrence: '#a0e1ff', amplification_burst: '#ffffff', sudden_decay: '#50648c',
};

export default function TimelineView() {
  const info = useSim((s) => s.info);
  const tick = useSim((s) => s.tick);
  const status = useSim((s) => s.status);
  const rewind = useSim((s) => s.rewind);
  const [m, setM] = useState<Metrics | null>(null);

  useEffect(() => {
    if (!info) return;
    void api.metrics(info.id).then(setM);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [info, Math.floor(tick / 6)]);

  const markers: Marker[] = useMemo(() => [
    ...(status?.checkpoints ?? []).map((t) => ({ t, color: '#303036' })),
    ...(m?.events ?? []).map((e) => ({ t: e.t, color: EVENT_COLORS[e.kind] ?? '#777' })),
  ], [m, status?.checkpoints]);

  if (!m) return <div className="panel-view dim">loading metrics…</div>;
  const onPick = (t: number) => {
    const cps = (status?.checkpoints ?? []).filter((c) => c <= t);
    if (cps.length && confirm(`Rewind to step ${t}? (restores checkpoint ${Math.max(...cps)} and replays deterministically)`)) void rewind(t);
  };
  return (
    <div className="panel-view timeline">
      <p className="dim small">Operational shape descriptors over time. Vertical marks: checkpoints (dark) and detected shape events
        (colored). Click a chart to rewind to that step. Descriptors are relative measures of this run, not forecasts.</p>
      <div className="grid2">
        {STEP_GROUPS.map((g) => (
          <Chart key={g.title} title={g.title} markers={markers} onPick={onPick}
            series={g.keys.map((k, i) => ({ label: k, t: m.t, v: m.series[k] ?? [], color: SHADES[i] }))} />
        ))}
        {GRAPH_GROUPS.map((g) => (
          <Chart key={g.title} title={g.title} markers={markers} onPick={onPick}
            series={g.keys.map((k, i) => ({ label: k, t: m.t_graph, v: m.graph_series[k] ?? [], color: SHADES[i] }))} />
        ))}
      </div>
      <h4>Shape events</h4>
      <ul className="events mono small cols">
        {[...m.events].reverse().slice(0, 80).map((e, k) => (
          <li key={k}><span style={{ color: EVENT_COLORS[e.kind] }}>■</span> <span className="dim">t{e.t}</span> {e.kind.replace(/_/g, ' ')}
            <span className="dim"> {Object.entries(e).filter(([x]) => x !== 't' && x !== 'kind').map(([x, v]) => `${x} ${v}`).join(' · ')}</span></li>
        ))}
      </ul>
    </div>
  );
}
