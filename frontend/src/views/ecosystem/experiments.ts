// XENOSCIENCE ECOSYSTEM — the experiments this environment can be pointed at, with the state each one is really in (read from the code on 2026-11-03). This is a registry of what exists, not a roadmap.
// Two things are kept apart and never merged: HOW the experiment is available (``mode``) and WHERE it is drawn (``scene``). A stored result is never passed off as a live experiment: only an entry
// whose mode is LIVE_ENGINE is run by an engine when asked, and only VERIFIED_REPLAY re-executes stored inputs and compares a digest. Every entry keeps its own state definition, intervention rules,
// observation and time span: connecting an experiment to this scene does not give it another one's.

export type ExperimentMode =
  /** an engine runs it when asked */
  | 'LIVE_ENGINE'
  /** stored inputs are re-executed by an engine and the result digest is compared with the stored one */
  | 'VERIFIED_REPLAY'
  /** fixed data kept for verification or display; nothing is executed */
  | 'FIXTURE'
  /** the implementation that would be needed does not exist here */
  | 'UNSUPPORTED';
export type ExperimentScene =
  /** drawn in this scene, with objects the user can pick and ask the engine about */
  | 'IN_SCENE'
  /** its record is shown by this scene, which has no object of its own for what the experiment varies */
  | 'RECORD_ONLY'
  /** drawn by another view of the application */
  | 'ELSEWHERE'
  | 'NONE';

export interface ExperimentEntry {
  id: string; title: string; mode: ExperimentMode; scene: ExperimentScene; engine: string;
  /** where the implementation lives (or the reason there is none) */
  source: string;
  /** the experiment's own definitions, which a common display must not replace */
  own: { state: string; interventions: string; observation: string; span: string };
  capabilities: { observe: boolean; intervene: boolean; compareBranches: boolean; replay: boolean };
  note: string;
}

const none = { observe: false, intervene: false, compareBranches: false, replay: false };
const meosOwn = (interventions: string, observation = 'the observation array of the engine (interval, lattice, region, aggregation, window, threshold, occluder)') =>
  ({ state: 'ACTIVE / DEGRADED / COLLAPSED from complete cycles in a window (status log)', interventions, observation, span: '240-480 ticks of one run' });

export const EXPERIMENTS: ExperimentEntry[] = [
  { id: 'meos-coupling', title: 'MEOS-0 coupling cut (interaction channel, feedback, sensors)', mode: 'LIVE_ENGINE', scene: 'IN_SCENE', engine: 'backend/xzr/meos (meos-0.5), /api/meos/run',
    source: 'engine components sensor_resource, interaction_channel, sensor_alteration, feedback; ops ISOLATE / RECONNECT', own: meosOwn('ISOLATE / RECONNECT of one of four couplings at a tick'),
    capabilities: { observe: true, intervene: true, compareBranches: true, replay: true }, note: 'Pick a coupling in the scene, ask the engine to cut it, compare the baseline and the branch.' },
  { id: 'meos-observation', title: 'MEOS-0 observation regimes', mode: 'LIVE_ENGINE', scene: 'IN_SCENE', engine: 'backend/xzr/meos/analysis.py observe(), /api/meos/run with an observation',
    source: 'the observation controls of this tab; the cells drawn in the scene are the engine\'s rule', own: meosOwn('none: a regime is applied to a run and does not change it'),
    capabilities: { observe: true, intervene: false, compareBranches: true, replay: true }, note: 'Interval, resolution, aggregation, window, threshold, region and occluder are set from the scene. Which interventions a regime makes possible is not evaluated.' },
  { id: 'meos-history', title: 'MEOS-0 history re-entry (retention, re-entry, effective consequence)', mode: 'LIVE_ENGINE', scene: 'IN_SCENE', engine: 'backend/xzr/meos (history trace, DISABLE_HISTORY)',
    source: 'the history section of this tab; the engine runs the baseline plus DISABLE_HISTORY', own: meosOwn('DISABLE_HISTORY at a tick'),
    capabilities: { observe: true, intervene: true, compareBranches: true, replay: true }, note: 'Retention and re-entry are read from the record; the consequence only from the second run. Addressability is not modelled.' },
  { id: 'meos-series', title: 'MEOS-0 experiment series: presets, saved MFS configurations, controlled runs', mode: 'LIVE_ENGINE', scene: 'IN_SCENE', engine: 'backend/xzr/meos: /run, /mfs-run, /reconfigure',
    source: 'the experiment-series section of this tab', own: { state: 'the status log; for a saved MFS, which components are retained; for a controlled run, the controller\'s decisions (ROUTE interventions)', interventions: 'a preset\'s scheduled interventions, none for a saved MFS, a stress at tick 100 and a controller for a controlled run', observation: 'the same observation array', span: '240-480 ticks' },
    capabilities: { observe: true, intervene: true, compareBranches: true, replay: true }, note: 'Each series is executed by the engine when loaded; the series keep their own definitions.' },
  { id: 'meos-replay', title: 'MEOS-0 verified replay of a record', mode: 'VERIFIED_REPLAY', scene: 'IN_SCENE', engine: 'backend/xzr/meos: /replay',
    source: 'VERIFY BY ENGINE REPLAY', own: meosOwn('none: the inputs of the record are re-executed'), capabilities: { observe: false, intervene: false, compareBranches: false, replay: true },
    note: 'The engine re-executes the record\'s configuration and interventions and compares the result digest; the reading of whole numbers is reported. Playing a record back runs nothing.' },
  { id: 'meos-revision', title: 'MEOS-0 world-responsive revision (phil mode)', mode: 'LIVE_ENGINE', scene: 'RECORD_ONLY', engine: 'backend/xzr/meos (phil: expression, scorekeeping, revision)',
    source: 'backend/xzr/meos/phil.py; set in the EXPERIMENT tab (philosophical)', own: meosOwn('none from this scene'), capabilities: { observe: true, intervene: false, compareBranches: false, replay: true },
    note: 'Runs in the same scene as any MEOS record; the scene has no object for the revision itself.' },
  { id: 'meos-reconfiguration', title: 'MEOS-0 cut and reconfiguration (routes, controllers, repair)', mode: 'LIVE_ENGINE', scene: 'RECORD_ONLY', engine: 'backend/xzr/meos (ROUTE, RECONFIGURE; stage 5-6 controllers)',
    source: 'RESEARCH tab; /api/meos/route-topology, /reconfigure, /repair-library', own: meosOwn('ROUTE, RECONFIGURE, repair actions'), capabilities: { observe: true, intervene: false, compareBranches: false, replay: true },
    note: 'Available through the research console; the 3D coupling layer does not request them.' },
  { id: 'disconnection', title: 'Disconnection (resolution study)', mode: 'FIXTURE', scene: 'ELSEWHERE', engine: 'stored summaries (useSummary: disconnection, topology_triggers)', source: 'the DISCONNECTION STUDY view',
    own: { state: 'the study\'s own resolution classes', interventions: 'those of the study, as stored', observation: 'those of the study', span: 'as stored' }, capabilities: none,
    note: 'Stored results are displayed by another view; nothing is run or replayed here.' },
  { id: 'escalation', title: 'Operational Resolution Escalation', mode: 'FIXTURE', scene: 'ELSEWHERE', engine: 'backend/xzr/experiments/escalation (stored results)', source: 'the resolution views of the research results',
    own: { state: 'the escalation\'s own resolution levels', interventions: 'those of the study, as stored', observation: 'those of the study', span: 'as stored' }, capabilities: none, note: 'Stored results are displayed by other views; nothing is run or replayed here.' },
  { id: 'multicluster', title: 'Multi-cluster / multi-system laboratory', mode: 'LIVE_ENGINE', scene: 'ELSEWHERE', engine: 'backend/xzr/lab/multisystem.py', source: '3D LABORATORY view (its own scene)',
    own: { state: 'the laboratory\'s own states (gantries, sensors, stores)', interventions: 'the laboratory\'s', observation: 'the laboratory\'s sensors', span: 'thousands of steps' }, capabilities: { observe: true, intervene: false, compareBranches: false, replay: true },
    note: 'Has its own 3D scene and engine; it is not drawn in this one (its objects are gantries and chambers, not arena cells).' },
  { id: 'xenosnn', title: 'Sensor-Body-XenoSNN', mode: 'FIXTURE', scene: 'NONE', engine: 'none here (ARDS replay target snn-fixture; the snnTorch server was not run)', source: 'backend/xzr/lineage.py lists it as a replay-level line',
    own: { state: 'a minimal neuron\'s membrane and spikes, as stored', interventions: 'none', observation: 'the stored trace', span: 'as stored' }, capabilities: none,
    note: 'A stored minimal-neuron fixture only; nothing here simulates a sensor, a body or a network.' },
  { id: 'to-c1', title: 'TO-C1 (direct coupling D vs common drive C, 729 words)', mode: 'UNSUPPORTED', scene: 'NONE', engine: 'not available',
    source: 'toc1.zip (SHA-256 ab3c32c97c7fec06b55e266e19db2515f900c503858aba3b586fe66fa93fcbf6) was announced and has not reached this machine; it is in no repository, history or folder searched',
    own: { state: 'not known here', interventions: 'not known here', observation: 'not known here', span: 'not known here' }, capabilities: none,
    note: 'SOURCE MISSING. No number of TO-C1 is reproduced or shown. The adapter is to be added from the original code, checked against the archived summary.' },
];

export const experimentById = (id: string): ExperimentEntry | undefined => EXPERIMENTS.find((e) => e.id === id);
export const MODE_TEXT: Record<ExperimentMode, string> = { LIVE_ENGINE: 'live engine', VERIFIED_REPLAY: 'verified replay', FIXTURE: 'fixture / stored', UNSUPPORTED: 'unsupported' };
export const SCENE_TEXT: Record<ExperimentScene, string> = { IN_SCENE: 'in this scene', RECORD_ONLY: 'record only', ELSEWHERE: 'another view', NONE: 'not drawn' };

// ------------------------------------------------------------------------------------------------ what a loaded series really is

export type SeriesKind = 'preset' | 'mfs' | 'controlled';
export interface SeriesEvidence { kind: SeriesKind; mode: ExperimentMode; text: string; storedResultCompared: boolean }

/** What the engine did when a series was loaded, from what the code does (not from the fact that it can be drawn in this scene). ``replayLine`` is the view's own status line, which for a controlled run carries
 *  the engine's own report of whether the recorded schedule replays identically without the controller. A saved MFS stores a digest of its DEFINITION, not of a run, so loading one compares nothing. */
export function seriesEvidence(kind: SeriesKind, replayLine: string | null): SeriesEvidence {
  if (kind === 'preset') return { kind, mode: 'LIVE_ENGINE', storedResultCompared: false, text: 'the engine executed the scheduled interventions on the default arrangement; no stored result was compared with it, so this is not a replay' };
  if (kind === 'mfs') return { kind, mode: 'LIVE_ENGINE', storedResultCompared: false, text: 'the engine executed the saved arrangement; the MFS library stores a digest of its definition, not of a run, so there is no stored result to compare with and this is not a verified replay' };
  const identical = !!replayLine && /replays identically/.test(replayLine), differs = !!replayLine && /DIFFERS/.test(replayLine);
  return { kind, mode: 'LIVE_ENGINE', storedResultCompared: false,
    text: `the engine executed the stress and the controller; ${identical ? 'it also verified that the controller\'s recorded schedule replays identically without the controller (a replay of the schedule, not of a stored experiment)' : differs ? 'it reports that the recorded schedule does NOT replay identically without the controller' : 'the engine\'s replay check of the schedule is not reported'}` };
}
