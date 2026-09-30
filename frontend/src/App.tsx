import { useCallback, useEffect, useState } from 'react';
import ControlBar from './components/ControlBar';
import Inspector from './components/Inspector';
import Legend from './components/Legend';
import ScaleNav from './components/ScaleNav';
import { t } from './i18n/strings';
import { GRAPH_VIEWS, useSim, type View } from './store/sim';
import CompareView from './views/CompareView';
import GraphView from './views/GraphView';
import PracticeView from './views/PracticeView';
import PhaseView from './views/research/PhaseView';
import PrimitiveView from './views/research/PrimitiveView';
import ReasonView from './views/research/ReasonView';
import ReductionView from './views/research/ReductionView';
import ShapePanel from './views/ShapePanel';
import TimelineView from './views/TimelineView';

const VIEWS: { id: View; label: () => string }[] = [
  { id: 'network', label: () => t('view_network') },
  { id: 'shape', label: () => t('view_shape') },
  { id: 'address', label: () => t('view_address') },
  { id: 'map', label: () => t('view_map') },
  { id: 'globe', label: () => t('view_globe') },
  { id: 'timeline', label: () => t('view_timeline') },
  { id: 'compare', label: () => t('view_compare') },
  { id: 'practice', label: () => t('view_practice') },
  { id: 'reduction', label: () => t('view_reduction') },
  { id: 'reason', label: () => t('view_reason') },
  { id: 'phases', label: () => t('view_phases') },
  { id: 'primitives', label: () => t('view_primitives') },
];

export default function App() {
  const info = useSim((s) => s.info);
  const view = useSim((s) => s.view);
  const setView = useSim((s) => s.setView);
  const open = useSim((s) => s.open);
  const error = useSim((s) => s.error);
  const jobs = useSim((s) => s.jobs);
  const compare = useSim((s) => s.compare);
  const overlay = useSim((s) => s.compareOverlay);
  const setOverlay = useSim((s) => s.setCompareOverlay);
  const [hoverAddr, setHoverAddr] = useState<string | null>(null);
  const onHover = useCallback((a: string | null) => setHoverAddr(a), []);

  useEffect(() => {
    const q = new URLSearchParams(location.search);
    void open(q.get('scenario') ?? 'demo-3k');
    const v = q.get('view') as View | null;
    if (v) setView(v);
  }, [open, setView]);

  const graph = GRAPH_VIEWS.includes(view);
  const running = Object.values(jobs).filter((j) => j.status === 'running').length;

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <h1>{t('title')}</h1>
          <div className="sub">{t('subtitle')}</div>
        </div>
        <nav className="views">
          {VIEWS.map((v) => (
            <button key={v.id} className={view === v.id ? 'on' : ''} onClick={() => setView(v.id)}>{v.label()}
              {v.id === 'compare' && running > 0 && <span className="badge">{running}</span>}</button>
          ))}
        </nav>
      </header>
      <ControlBar />
      {error && <div className="error">{error}</div>}
      <main className={graph ? 'with-side' : ''}>
        {!info ? <div className="panel-view dim">building scenario…</div> : (
          <>
            {graph && (
              <section className="stage">
                <div className="stage-top">
                  <ScaleNav hoverAddress={hoverAddr} />
                  {compare && (
                    <label className="small overlay-toggle"><input type="checkbox" checked={overlay}
                      onChange={(e) => setOverlay(e.target.checked)} /> show last comparison in graph</label>
                  )}
                </div>
                <GraphView key={view} projection={view as 'network'} onClusterHover={onHover} />
                <Legend />
              </section>
            )}
            {graph && (view === 'shape' ? <div className="side2"><ShapePanel /><Inspector /></div> : <Inspector />)}
            {view === 'timeline' && <TimelineView />}
            {view === 'compare' && <CompareView />}
            {view === 'practice' && <PracticeView />}
            {view === 'reduction' && <ReductionView />}
            {view === 'reason' && <ReasonView />}
            {view === 'phases' && <PhaseView />}
            {view === 'primitives' && <PrimitiveView />}
          </>
        )}
      </main>
      <footer className="foot">
        <span>{t('footer')}</span>
        {info && <span className="dim mono">{info.scenario.name} · runtime {info.runtime_is_full === false ? 'minimal' : 'full'} · session {info.id}</span>}
      </footer>
    </div>
  );
}
