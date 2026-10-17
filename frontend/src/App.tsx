import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import ControlBar from './components/ControlBar';
import Inspector from './components/Inspector';
import Legend from './components/Legend';
import Orientation from './components/Orientation';
import ScaleNav from './components/ScaleNav';
import ShareStrip from './components/ShareStrip';
import ViewBoundary from './components/ViewBoundary';
import { NATIVE, WEBRT, nativeOpenResults } from './api/native';
import { t } from './i18n/strings';
import staticViews from './static-views.json';
import { pageTitle, searchForView, unknownRoute, viewFromSearch } from './routing';
import { GRAPH_VIEWS, useSim, type View } from './store/sim';
import PracticeView from './views/PracticeView';
import PhaseView from './views/research/PhaseView';
import PrimitiveView from './views/research/PrimitiveView';
import ReasonView from './views/research/ReasonView';
import ReductionView from './views/research/ReductionView';
import HPOView from './views/research/HPOView';
const LabView = lazy(() => import('./views/lab/LabView'));
import CompressionView from './views/resolution/CompressionView';
import DisconnectionView from './views/resolution/DisconnectionView';
import HiddenDifferenceView from './views/resolution/HiddenDifferenceView';
import ReasoningStructureView from './views/resolution/ReasoningStructureView';
import ResolutionMatrixView from './views/resolution/ResolutionMatrixView';
import ScalePenetrationView from './views/resolution/ScalePenetrationView';
import OverviewView from './views/OverviewView';
import ShapePanel from './views/ShapePanel';
import TimelineView from './views/TimelineView';

// The WebGL projections (deck.gl, world atlas) load only when a graph or comparison view opens.
const GraphView = lazy(() => import('./views/GraphView'));
const CompareView = lazy(() => import('./views/CompareView'));

// The in-tab runtime's start-up progress exists only in the browser build (the literal test removes it from the others).
const WebBoot = import.meta.env.VITE_WEBRT === '1' ? lazy(() => import('./components/WebBoot')) : () => null;
const loadingView = <div className="panel-view dim">loading view…</div>;

const VIEWS: { id: View; label: () => string }[] = [
  { id: 'overview', label: () => t('view_overview') },
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
  { id: 'res_matrix', label: () => t('view_res_matrix') },
  { id: 'res_hidden', label: () => t('view_res_hidden') },
  { id: 'res_penetration', label: () => t('view_res_penetration') },
  { id: 'res_structure', label: () => t('view_res_structure') },
  { id: 'res_disconnection', label: () => t('view_res_disconnection') },
  { id: 'res_compression', label: () => t('view_res_compression') },
  { id: 'hpo', label: () => t('view_hpo') },
  { id: 'laboratory', label: () => t('view_laboratory') },
];

// Static read-only mirror (VITE_STATIC=1): no backend session; only the research views, read from exported result
// files. The normal build is unchanged.
const STATIC = import.meta.env.VITE_STATIC === '1';
// (also read by backend/scripts/export_static.py, which routes exactly these views on the host)
const RESEARCH = staticViews as View[];
// Views this build can show (the project overview page is exported only with the static site), and the view of the
// bare URL. Every other view is addressed as ?view=<id>.
// The iOS app (VITE_NATIVE=1) runs the simulator in-process and shows its interactive views; the research results
// stay on the public research-results site, opened from the app in the system browser.
const RESULTS_SITE = 'https://ziran-xeno-simulator.vercel.app';
const AVAILABLE: View[] = STATIC ? RESEARCH
  : VIEWS.map((v) => v.id).filter((v) => v !== 'overview' && !(NATIVE && RESEARCH.includes(v)));
const DEFAULT_VIEW: View = STATIC ? 'overview' : 'network';
const labelOf = (v: View) => VIEWS.find((x) => x.id === v)?.label() ?? v;

// The first render already shows the view the URL names, so a deep link never passes through another view.
useSim.setState({ view: viewFromSearch(location.search, AVAILABLE, DEFAULT_VIEW) });

export default function App() {
  const info = useSim((s) => s.info);
  const view = useSim((s) => s.view);
  const setView = useSim((s) => s.setView);
  const resumeOrOpen = useSim((s) => s.resumeOrOpen);
  const error = useSim((s) => s.error);
  const notice = useSim((s) => s.notice);
  const sessionGone = useSim((s) => s.sessionGone);
  const jobs = useSim((s) => s.jobs);
  const compare = useSim((s) => s.compare);
  const overlay = useSim((s) => s.compareOverlay);
  const setOverlay = useSim((s) => s.setCompareOverlay);
  const [hoverAddr, setHoverAddr] = useState<string | null>(null);
  const onHover = useCallback((a: string | null) => setHoverAddr(a), []);

  const [missing, setMissing] = useState(() => unknownRoute(location.pathname, location.search, AVAILABLE));

  useEffect(() => {
    if (!STATIC) void resumeOrOpen(new URLSearchParams(location.search).get('scenario'));
  }, [resumeOrOpen]);

  // iOS: the runtime pauses when the app leaves the foreground (the process is suspended; nothing runs meanwhile)
  useEffect(() => {
    if (!NATIVE) return;
    const on = (e: Event) => {
      const { state, detail } = (e as CustomEvent<{ state: string; detail?: { paused?: string[] } }>).detail;
      if (state === 'foreground' && detail?.paused?.length) {
        useSim.setState({ notice: WEBRT ? 'The simulation was paused while this tab was in the background. Press Run to continue.'
          : 'The simulation was paused while the app was in the background. Press Run to continue.' });
      } else if (state === 'memory') {
        useSim.setState({ notice: 'The device reported memory pressure: the simulation was paused. Press Run to continue.' });
      }
    };
    window.addEventListener('xzr-lifecycle', on);
    return () => window.removeEventListener('xzr-lifecycle', on);
  }, []);

  // Back/Forward: the URL is the source of truth.
  useEffect(() => {
    const onPop = () => {
      setMissing(unknownRoute(location.pathname, location.search, AVAILABLE));
      setView(viewFromSearch(location.search, AVAILABLE, DEFAULT_VIEW));
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, [setView]);

  // Any view change (tabs, or a view opening another one) becomes a history entry with its own URL and title.
  useEffect(() => {
    if (missing) {
      document.title = pageTitle('Not found');
      return;
    }
    const s = searchForView(location.search, view, DEFAULT_VIEW);
    if (s !== location.search) {
      // a new view is a new history entry; the same view under a non-canonical URL is only rewritten
      const same = viewFromSearch(location.search, AVAILABLE, DEFAULT_VIEW) === view;
      history[same ? 'replaceState' : 'pushState'](null, '', location.pathname + s);
    }
    document.title = pageTitle(labelOf(view));
    // on narrow screens the tab strip scrolls: keep the active tab visible in it
    document.querySelector('.views button.on')?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }, [view, missing]);

  const go = (v: View) => {
    if (missing) {  // leave the unknown URL for the view's own URL
      const q = new URLSearchParams(location.search);
      q.delete('view');
      const rest = q.toString();
      history.pushState(null, '', '/' + searchForView(rest ? `?${rest}` : '', v, DEFAULT_VIEW));
      setMissing(null);
    }
    setView(v);
  };

  const graph = GRAPH_VIEWS.includes(view);
  const running = Object.values(jobs).filter((j) => j.status === 'running').length;

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <h1>{t('title')}</h1>
          <div className="sub">{STATIC ? 'Operational-shape research results · read-only' : t(NATIVE ? 'subtitle_native' : 'subtitle')}</div>
        </div>
        <nav className="views">
          {VIEWS.filter((v) => AVAILABLE.includes(v.id)).map((v) => (
            <button key={v.id} className={view === v.id && !missing ? 'on' : ''} onClick={() => go(v.id)}
              onFocus={(e) => e.currentTarget.scrollIntoView({ block: 'nearest', inline: 'nearest' })}
              aria-current={view === v.id && !missing ? 'page' : undefined}>{v.label()}
              {v.id === 'compare' && running > 0 && <span className="badge">{running}</span>}</button>
          ))}
          {STATIC && <button className="external" onClick={() => location.assign('/app/')}
            title="The simulator runs in your browser tab at /app/ (smaller workloads, nothing is sent to a server)">
            Run the simulator ↗</button>}
          {NATIVE && <button className="external" onClick={nativeOpenResults}
            title={`Research results are published at ${RESULTS_SITE} (opens in the browser)`}>
            {t('research_results')} ↗</button>}
        </nav>
      </header>
      {STATIC ? (
        view === 'overview' && !missing ? null : (
          <div className="static-note small">Read-only research-result layer of XENO ZIRAN SIMULATOR, read from its
            experiment result files. No simulation runs on this page. The interactive simulator runs in your browser at{' '}
            <a href="/app/">/app/</a> (smaller workloads), or on a local server for full-size runs.</div>
        )
      ) : view !== 'laboratory' && <ControlBar />}
      {WEBRT && (
        <div className="static-note small">This simulator runs in your browser tab: the engine is downloaded from this site once and
          nothing you enter is sent anywhere. Workloads are smaller than in the desktop runtime, and floating-point results can
          differ from the desktop runtime in the last digits (runs here replay exactly within this build). Published research
          results are on the <a href="/">results site</a>.</div>
      )}
      {error && (
        <div className="error">{error}
          {sessionGone && <> <button onClick={() => void resumeOrOpen(null)}>Start a new session</button></>}
        </div>
      )}
      {notice && <div className="notice small">{notice}</div>}
      {!missing && <ShareStrip view={view} />}
      <main className={graph && !missing ? 'with-side' : ''}>
        {missing ? (
          <div className="panel-view not-found" role="alert">
            <h2>Not found</h2>
            {!VIEWS.some((v) => `?view=${v.id}` === missing)
              ? <p><span className="mono">{missing}</span> is not a view of XENO ZIRAN SIMULATOR.</p>
              : NATIVE
                ? <p><span className="mono">{missing}</span> is a research-result view. Research results are published
                  on the research-results site ({RESULTS_SITE}), not inside the app.</p>
              : STATIC
                ? <p><span className="mono">{missing}</span> is a view of the interactive runtime. It runs in your browser
                  at <a href="/app/">/app/</a> (or on a local server) and is not part of this read-only page.</p>
                : <p><span className="mono">{missing}</span> is the entry view of the hosted research-results site and
                  is not part of the local runtime build.</p>}
            <p className="small">Views in this build:</p>
            <ul className="small">
              {AVAILABLE.map((v) => <li key={v}><a href={'/' + searchForView('', v, DEFAULT_VIEW)}
                onClick={(e) => { e.preventDefault(); go(v); }}>{labelOf(v)}</a></li>)}
            </ul>
          </div>
        ) : !info && !STATIC ? <div className="panel-view dim">{WEBRT ? <Suspense fallback={null}><WebBoot /></Suspense> : 'building scenario…'}</div> : (
          <ViewBoundary view={view}><Suspense fallback={loadingView}>
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
            {view === 'res_matrix' && <ResolutionMatrixView />}
            {view === 'res_hidden' && <HiddenDifferenceView />}
            {view === 'res_penetration' && <ScalePenetrationView />}
            {view === 'res_structure' && <ReasoningStructureView />}
            {view === 'res_disconnection' && <DisconnectionView />}
            {view === 'res_compression' && <CompressionView />}
            {view === 'hpo' && <HPOView />}
            {view === 'laboratory' && <LabView />}
            {view === 'overview' && (
              <div className="entry">
                <Orientation views={AVAILABLE.filter((v) => v !== 'overview').map((v) => ({ id: v, label: labelOf(v) }))}
                  onOpen={go} />
                <OverviewView />
              </div>
            )}
          </Suspense></ViewBoundary>
        )}
      </main>
      <footer className="foot">
        <span>{t(STATIC ? 'footer_static' : 'footer')}</span>
        {info?.hierarchy_source?.startsWith('on-device') && (
          <span className="warn" title={info.hierarchy_source}>address hierarchy computed on this device — it may
            differ from the desktop runtime's for this scenario</span>
        )}
        {info && <span className="dim mono">{info.scenario.name} · runtime {info.runtime_is_full === false ? 'minimal' : 'full'} · session {info.id.slice(0, 8)}</span>}
      </footer>
    </div>
  );
}
