// XENOSCIENCE ECOSYSTEM — the experiments the 3D environment can be pointed at, with the state each one is really in. This is a registry of what exists in the repository (read from the code on
// 2026-11-02), not a roadmap: an entry says what can be done with it today, and the ones that cannot be run are listed as what they are. A new experiment is added as one more entry whose
// ``source`` names the original files, with their digests, and whose capabilities are switched on only when the adapter for them exists and has a test against the original's own outputs.

export type ExperimentStatus =
  /** observed, intervened on and compared in the 3D scene through the engine */
  | 'SCENE_ACTIVE'
  /** a live engine exists and is used by other panes of this view; the 3D scene does not draw it */
  | 'ENGINE_ONLY'
  /** stored results are shown by an analysis view; there is no engine to intervene on from here */
  | 'RESULTS_ONLY'
  /** a stored fixture can be replayed; there is no live engine in this environment */
  | 'FIXTURE_ONLY'
  /** the original source was requested and has not been supplied */
  | 'SOURCE_MISSING';

export interface ExperimentEntry {
  id: string; title: string; status: ExperimentStatus; engine: string;
  /** where the implementation lives (or the reason there is none) */
  source: string;
  capabilities: { observe: boolean; intervene: boolean; compareBranches: boolean; replay: boolean };
  note: string;
}

const none = { observe: false, intervene: false, compareBranches: false, replay: false };

export const EXPERIMENTS: ExperimentEntry[] = [
  { id: 'meos-coupling', title: 'MEOS-0 coupling cut (interaction channel, feedback, sensors)', status: 'SCENE_ACTIVE', engine: 'backend/xzr/meos (meos-0.5), /api/meos/run',
    source: 'backend/xzr/meos/engine.py: components sensor_resource, interaction_channel, sensor_alteration, feedback; ops ISOLATE / RECONNECT',
    capabilities: { observe: true, intervene: true, compareBranches: true, replay: true },
    note: 'Pick a coupling in the scene, ask the engine to cut it, compare the baseline and the branch. Observation regimes are changed in EXPERIMENT.' },
  { id: 'meos-revision', title: 'MEOS-0 world-responsive revision (phil mode)', status: 'ENGINE_ONLY', engine: 'backend/xzr/meos (phil: expression, scorekeeping, revision)',
    source: 'backend/xzr/meos/phil.py; set in the EXPERIMENT tab (philosophical)', capabilities: { observe: true, intervene: false, compareBranches: false, replay: true },
    note: 'Runs in the same scene as any MEOS record; the scene has no object for the revision itself.' },
  { id: 'meos-reconfiguration', title: 'MEOS-0 cut and reconfiguration (routes, controllers, repair)', status: 'ENGINE_ONLY', engine: 'backend/xzr/meos (ROUTE, RECONFIGURE; stage 5-6 controllers)',
    source: 'RESEARCH tab; /api/meos/route-topology, /reconfigure, /repair-library', capabilities: { observe: true, intervene: false, compareBranches: false, replay: true },
    note: 'Available through the research console; the 3D coupling layer does not yet request them.' },
  { id: 'escalation', title: 'Operational Resolution Escalation', status: 'RESULTS_ONLY', engine: 'backend/xzr/experiments/escalation (stored results)',
    source: 'the resolution views of the research results (RESOLUTION MATRIX and the others)', capabilities: none, note: 'Stored results are displayed; nothing is run from this view.' },
  { id: 'multicluster', title: 'Multi-cluster / multi-system laboratory', status: 'ENGINE_ONLY', engine: 'backend/xzr/lab/multisystem.py',
    source: '3D LABORATORY view (its own scene)', capabilities: { observe: true, intervene: false, compareBranches: false, replay: true },
    note: 'Has its own 3D scene and engine; it is not drawn in this one.' },
  { id: 'xenosnn', title: 'Sensor-Body-XenoSNN', status: 'FIXTURE_ONLY', engine: 'none here (ARDS replay target snn-fixture; the snnTorch server was not run)',
    source: 'backend/xzr/lineage.py lists it as a replay-level line', capabilities: { ...none, replay: true }, note: 'A stored minimal-neuron fixture only; nothing here simulates a sensor, a body or a network.' },
  { id: 'to-c1', title: 'TO-C1 (direct coupling D vs common drive C, 729 words)', status: 'SOURCE_MISSING', engine: 'not available',
    source: 'toc1.zip (SHA-256 ab3c32c97c7fec06b55e266e19db2515f900c503858aba3b586fe66fa93fcbf6) was announced and has not reached this machine; it is in no repository, history or folder searched',
    capabilities: none, note: 'No number of TO-C1 is reproduced or shown. The adapter is to be added from the original code, checked against the archived summary.' },
];

export const experimentById = (id: string): ExperimentEntry | undefined => EXPERIMENTS.find((e) => e.id === id);
export const STATUS_TEXT: Record<ExperimentStatus, string> = {
  SCENE_ACTIVE: 'in the 3D scene', ENGINE_ONLY: 'engine only', RESULTS_ONLY: 'stored results', FIXTURE_ONLY: 'fixture only', SOURCE_MISSING: 'source missing',
};
