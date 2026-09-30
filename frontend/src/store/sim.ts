// Application state. High-frequency simulation data lives in the Mirror (mutated in place and read by the
// render loop); React-visible state here is updated at a throttled rate.

import { create } from 'zustand';
import { api, connect, type CommandReport, type CompareResult, type Job, type SessionInfo, type Status } from '../api/client';
import { Mirror } from '../lod/mirror';

export type View = 'network' | 'shape' | 'address' | 'map' | 'globe' | 'timeline' | 'compare' | 'practice'
  | 'reduction' | 'reason' | 'phases' | 'primitives';
export const GRAPH_VIEWS: View[] = ['network', 'shape', 'address', 'map', 'globe'];

export interface ConsoleEntry { id: number; text: string; report?: CommandReport; error?: string; suggestions?: string[] }

interface StreamStats { framesPerSec: number; bytesPerSec: number; stepsPerFrame: number }

interface State {
  info: SessionInfo | null;
  status: Status | null;
  mirror: Mirror | null;
  ws: WebSocket | null;
  connected: boolean;
  view: View;
  scale: number; // 0..5 (macro … relation)
  requestedScale: number | null;
  selected: number | null;
  hoverCluster: string | null;
  step: Record<string, number>;
  graph: Record<string, number>;
  tick: number; // throttled UI refresh counter
  layoutTick: number;
  resyncTick: number;
  stream: StreamStats;
  fps: number;
  jobs: Record<string, Job>;
  compare: CompareResult | null;
  compareOverlay: boolean;
  consoleLog: ConsoleEntry[];
  practiceTick: number;
  error: string | null;
  // actions
  open: (sample: string) => Promise<void>;
  openSaved: (saved: { scenario: unknown; applied?: unknown }) => Promise<void>;
  control: (action: string, extra?: { steps?: number; speed?: number }) => Promise<void>;
  rewind: (t: number) => Promise<void>;
  setView: (v: View) => void;
  setScale: (s: number) => void;
  requestScale: (s: number | null) => void;
  select: (i: number | null) => void;
  setHoverCluster: (a: string | null) => void;
  setFps: (f: number) => void;
  runCommand: (text: string) => Promise<void>;
  loadCompare: (jid: string) => Promise<void>;
  setCompareOverlay: (b: boolean) => void;
  startCompare: (horizon: number) => Promise<void>;
}

let entryId = 0;
let lastUi = 0;
let frameWindow: { wall: number; bytes: number; steps: number }[] = [];

export const useSim = create<State>((set, get) => ({
  info: null, status: null, mirror: null, ws: null, connected: false,
  view: 'network', scale: 0, requestedScale: null, selected: null, hoverCluster: null,
  step: {}, graph: {}, tick: 0, layoutTick: 0, resyncTick: 0,
  stream: { framesPerSec: 0, bytesPerSec: 0, stepsPerFrame: 0 }, fps: 0,
  jobs: {}, compare: null, compareOverlay: false, consoleLog: [], practiceTick: 0, error: null,

  open: async (sample) => {
    get().ws?.close();
    set({ error: null, info: null, mirror: null, compare: null, selected: null, jobs: {} });
    try {
      const runtime = new URLSearchParams(location.search).get('runtime') ?? undefined;
      const info = await api.createSession(sample, runtime);
      attach(info);
    } catch (e) {
      set({ error: String(e) });
    }
  },

  openSaved: async (saved) => {
    get().ws?.close();
    try {
      attach(await api.loadSession(saved));
    } catch (e) {
      set({ error: String(e) });
    }
  },

  control: async (action, extra) => {
    const info = get().info;
    if (!info) return;
    try {
      set({ status: await api.control(info.id, action, extra) });
    } catch (e) {
      set({ error: String(e) });
    }
  },

  rewind: async (t) => {
    const info = get().info;
    if (!info) return;
    set({ status: await api.rewind(info.id, t) });
  },

  setView: (v) => set({ view: v }),
  setScale: (s) => { if (s !== get().scale) set({ scale: s }); },
  requestScale: (s) => set({ requestedScale: s }),
  select: (i) => set({ selected: i }),
  setHoverCluster: (a) => set({ hoverCluster: a }),
  setFps: (f) => set({ fps: f }),
  setCompareOverlay: (b) => set({ compareOverlay: b }),

  runCommand: async (text) => {
    const info = get().info;
    if (!info) return;
    const id = ++entryId;
    set({ consoleLog: [...get().consoleLog, { id, text }] });
    const update = (patch: Partial<ConsoleEntry>) =>
      set({ consoleLog: get().consoleLog.map((e) => (e.id === id ? { ...e, ...patch } : e)) });
    try {
      const report = await api.command(info.id, text);
      update({ report });
      if (report.job) set({ jobs: { ...get().jobs, [report.job]: { id: report.job, kind: 'compare', status: 'running', horizon: 0 } } });
      set({ practiceTick: get().practiceTick + 1 });
    } catch (e) {
      const body = (e as { body?: { error?: string; suggestions?: string[] } }).body;
      update({ error: body?.error ?? String(e), suggestions: body?.suggestions });
    }
  },

  startCompare: async (horizon) => {
    const info = get().info;
    if (!info) return;
    const { job } = await api.compare(info.id, horizon);
    set({ jobs: { ...get().jobs, [job]: { id: job, kind: 'compare', status: 'running', horizon } } });
  },

  loadCompare: async (jid) => {
    const info = get().info;
    if (!info) return;
    const res = await api.compareResult(info.id, jid);
    set({ compare: res, compareOverlay: true });
  },
}));

function attach(info: SessionInfo) {
  const mirror = new Mirror(info.n);
  const set = useSim.setState;
  const get = useSim.getState;
  set({ info, mirror, status: { ...info, pending_steps: 0 }, connected: false });
  (window as unknown as { __xzr: unknown }).__xzr = { mirror, get };
  const ws = connect(info.id, (m) => {
    const now = performance.now();
    if (m.kind === 'frame') {
      const f = m.frame;
      if (f.type === 'snapshot') {
        mirror.applySnapshot(f.snapshot);
        set({ resyncTick: get().resyncTick + 1 });
      } else if (f.type === 'deltas') {
        mirror.applySteps(f.steps, now, f.bytes);
        frameWindow.push({ wall: now, bytes: f.bytes, steps: f.steps.length });
      } else {
        mirror.applyAggregates(f.aggregates, now);
      }
    } else {
      const msg = m.msg;
      if (msg.type === 'metrics') {
        frameWindow = frameWindow.filter((x) => x.wall > now - 2000);
        const span = frameWindow.length > 1 ? (now - frameWindow[0].wall) / 1000 : 1;
        const stream = {
          framesPerSec: frameWindow.length > 1 ? (frameWindow.length - 1) / span : 0,
          bytesPerSec: frameWindow.reduce((a, x) => a + x.bytes, 0) / Math.max(span, 1e-3),
          stepsPerFrame: frameWindow.length ? frameWindow.reduce((a, x) => a + x.steps, 0) / frameWindow.length : 0,
        };
        const patch: Partial<State> = {};
        if (msg.graph) patch.graph = msg.graph as Record<string, number>;
        if (msg.layout_changed) patch.layoutTick = get().layoutTick + 1;
        if (now - lastUi > 120 || msg.graph || msg.layout_changed) {
          lastUi = now;
          Object.assign(patch, {
            step: (msg.step ?? {}) as Record<string, number>,
            status: msg as unknown as Status, tick: get().tick + 1, stream,
          });
        }
        if (Object.keys(patch).length) set(patch);
      } else if (msg.type === 'resync') {
        mirror.clearEdges();
        set({ status: msg as unknown as Status, resyncTick: get().resyncTick + 1 });
      } else if (msg.type === 'job') {
        const job = msg as unknown as Job;
        set({ jobs: { ...get().jobs, [job.id]: job } });
        if (job.status === 'done') void get().loadCompare(job.id);
      } else if (msg.type === 'hello') {
        set({ connected: true });
      }
    }
  }, () => set({ connected: false }));
  set({ ws });
}
