// State of the XenoBody view. High-rate data (frames, observation samples) lives in module-level buffers read by the render loop;
// React-visible state is updated at a throttled rate.
import { create } from 'zustand';
import { ApiError } from '../../api/client';
import { xb, type BodyInfo, type Catalog, type HistoryView, type Inspect, type Job, type StepResult, type XbRecord } from '../../api/xbtro';
import { FrameBuffer, ObservationStore } from './logic';
import type { Layer } from './BodyScene';
import { saveText } from './download';

export const frames = new FrameBuffer(14);
export const obsStore = new ObservationStore();

export type Tab = 'body' | 'experiments' | 'results' | 'history' | 'scope';

interface XbState {
  catalog: Catalog | null;
  wid: string | null;
  error: string | null;
  notice: string | null;
  tab: Tab;
  body: BodyInfo | null;
  bid: string | null;
  running: boolean;
  speed: number;
  status: StepResult['status'] | null;
  layer: Layer;
  overlay: boolean;
  selected: string | null;
  inspect: Inspect | null;
  tick: number;
  jobs: Record<string, Job>;
  history: HistoryView | null;
  record: XbRecord | null;
  compareWith: XbRecord | null;
  busy: boolean;
  init: () => Promise<void>;
  setTab: (t: Tab) => void;
  createBody: (opts: Record<string, unknown>) => Promise<void>;
  closeBody: () => Promise<void>;
  run: () => void;
  pause: () => void;
  stepOnce: (n?: number) => Promise<void>;
  setSpeed: (s: number) => void;
  setLayer: (l: Layer) => void;
  setOverlay: (b: boolean) => void;
  command: (cmd: Record<string, unknown>) => Promise<boolean>;
  select: (part: string | null) => void;
  saveBody: () => Promise<void>;
  startExperiment: (exp: string, params: Record<string, unknown>) => Promise<void>;
  cancelJob: (jid: string) => Promise<void>;
  openRecord: (rid: string, as?: 'main' | 'compare') => Promise<void>;
  refreshHistory: () => Promise<void>;
  rerun: (rid: string) => Promise<void>;
  reanalyse: (rid: string, observation: unknown) => Promise<void>;
  reenter: (rid: string, exp: string, params: Record<string, unknown>) => Promise<void>;
  deleteRecord: (rid: string) => Promise<void>;
  exportRecord: (rid: string, fmt: 'json' | 'csv') => Promise<void>;
  exportHistory: () => Promise<void>;
  importText: (text: string) => Promise<void>;
  dismiss: () => void;
}

const message = (e: unknown) => (e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));
let timer: ReturnType<typeof setTimeout> | null = null;
let lastUi = 0;
let lastInspect = 0;
const pollers = new Map<string, ReturnType<typeof setInterval>>();

export const useXb = create<XbState>((set, get) => {
  const fail = (e: unknown) => set({ error: message(e), running: false, busy: false });

  async function pump(): Promise<void> {
    const s = get();
    if (!s.running || !s.bid || !s.wid || !s.body || s.busy) return;
    set({ busy: true });
    const t0 = performance.now();
    try {
      const maxStep = Number(s.catalog?.limits.max_step ?? 30);
      const n = Math.max(1, Math.min(maxStep, Math.round((s.speed * 0.05) / s.body.dt)));
      const r = await xb.step(s.wid, s.bid, n);
      frames.push(r.frames);
      obsStore.push(r.observation);
      const now = performance.now();
      const patch: Partial<XbState> = { busy: false, status: r.status };
      if (now - lastUi > 90 || r.finished) { patch.tick = get().tick + 1; lastUi = now; }
      if (r.finished) { patch.running = false; patch.notice = r.status.fell[0] ? 'The body fell (a physical fall in the model).' : r.status.diverged[0] ? 'The run diverged numerically — this is a failure of the numerics, not a fall.' : 'The horizon of this body was reached.'; }
      set(patch);
      if (get().selected && now - lastInspect > 700) { lastInspect = now; void refreshInspect(); }
    } catch (e) { fail(e); return; }
    if (get().running) timer = setTimeout(() => void pump(), Math.max(0, 50 - (performance.now() - t0)));
  }

  async function refreshInspect(): Promise<void> {
    const { wid, bid, selected } = get();
    if (!wid || !bid || !selected) return;
    try { set({ inspect: await xb.inspect(wid, bid, selected, 5) }); } catch { /* the body may have been closed meanwhile */ }
  }

  function track(job: Job): void {
    set({ jobs: { ...get().jobs, [job.id]: job } });
    const wid = get().wid;
    if (!wid) return;
    const id = setInterval(async () => {
      try {
        const j = await xb.job(wid, job.id);
        set({ jobs: { ...get().jobs, [job.id]: j } });
        if (j.status === 'done' || j.status === 'error' || j.status === 'cancelled') {
          clearInterval(id); pollers.delete(job.id);
          if (j.status === 'done' && j.record_id) { await get().refreshHistory(); await get().openRecord(j.record_id); set({ tab: 'results' }); }
          if (j.status === 'error') set({ error: j.error ?? 'the job failed' });
        }
      } catch (e) { clearInterval(id); pollers.delete(job.id); set({ error: message(e) }); }
    }, 450);
    pollers.set(job.id, id);
  }

  return {
    catalog: null, wid: null, error: null, notice: null, tab: 'body', body: null, bid: null, running: false, speed: 1, status: null,
    layer: 'reference', overlay: true, selected: null, inspect: null, tick: 0, jobs: {}, history: null, record: null, compareWith: null, busy: false,

    init: async () => {
      if (get().wid) return;
      try {
        const [catalog, ws] = await Promise.all([xb.catalog(), xb.createWorkspace()]);
        set({ catalog, wid: ws.id });
        await get().refreshHistory();
      } catch (e) { set({ error: message(e) }); }
    },
    setTab: (tab) => { if (tab !== 'body') get().pause(); set({ tab }); },
    createBody: async (opts) => {
      const { wid, bid } = get();
      if (!wid) return;
      try {
        get().pause();
        if (bid) { await xb.closeBody(wid, bid).catch(() => undefined); }
        frames.clear(); obsStore.clear();
        const b = await xb.createBody(wid, opts);
        set({ body: b, bid: b.id, status: null, selected: null, inspect: null, error: null, notice: null, tick: get().tick + 1 });
      } catch (e) { set({ error: message(e) }); }
    },
    closeBody: async () => {
      const { wid, bid } = get();
      get().pause();
      if (wid && bid) await xb.closeBody(wid, bid).catch(() => undefined);
      frames.clear(); obsStore.clear();
      set({ body: null, bid: null, status: null, selected: null, inspect: null });
    },
    run: () => { if (!get().running && get().bid) { set({ running: true, error: null }); void pump(); } },
    pause: () => { if (timer) clearTimeout(timer); timer = null; set({ running: false }); },
    stepOnce: async (n = 5) => {
      const { wid, bid } = get();
      if (!wid || !bid || get().busy) return;
      try {
        set({ busy: true });
        const r = await xb.step(wid, bid, n);
        frames.push(r.frames); obsStore.push(r.observation);
        set({ busy: false, status: r.status, tick: get().tick + 1 });
        if (get().selected) void refreshInspect();
      } catch (e) { fail(e); }
    },
    setSpeed: (speed) => set({ speed }),
    setLayer: (layer) => set({ layer }),
    setOverlay: (overlay) => set({ overlay }),
    command: async (cmd) => {
      const { wid, bid } = get();
      if (!wid || !bid) return false;
      try {
        await xb.command(wid, bid, cmd);
        if (cmd.type === 'observation' || cmd.type === 'line' || cmd.type === 'intervention') {
          const i = await xb.bodyInfo(wid, bid);
          set({ body: { ...i.info, id: bid }, error: null, tick: get().tick + 1 });
        }
        return true;
      } catch (e) { set({ error: message(e) }); return false; }
    },
    select: (part) => { set({ selected: part, inspect: part ? get().inspect : null }); if (part) void refreshInspect(); },
    saveBody: async () => {
      const { wid, bid } = get();
      if (!wid || !bid) return;
      try { await xb.saveBody(wid, bid); await get().refreshHistory(); set({ notice: 'The run was saved to the history as a record (experiment L).' }); } catch (e) { set({ error: message(e) }); }
    },
    startExperiment: async (exp, params) => {
      const { wid } = get();
      if (!wid) return;
      try { const r = await xb.startExperiment(wid, exp, params); track(r.job); set({ error: null }); } catch (e) { set({ error: message(e) }); }
    },
    cancelJob: async (jid) => { const { wid } = get(); if (wid) await xb.cancel(wid, jid).catch((e) => set({ error: message(e) })); },
    openRecord: async (rid, as = 'main') => {
      const { wid } = get();
      if (!wid) return;
      try { const rec = await xb.record(wid, rid); set(as === 'main' ? { record: rec } : { compareWith: rec }); } catch (e) { set({ error: message(e) }); }
    },
    refreshHistory: async () => { const { wid } = get(); if (wid) try { set({ history: await xb.history(wid) }); } catch (e) { set({ error: message(e) }); } },
    rerun: async (rid) => { const { wid } = get(); if (wid) try { track((await xb.rerun(wid, rid)).job); } catch (e) { set({ error: message(e) }); } },
    reanalyse: async (rid, observation) => { const { wid } = get(); if (wid) try { track((await xb.reanalyse(wid, rid, observation)).job); } catch (e) { set({ error: message(e) }); } },
    reenter: async (rid, exp, params) => { const { wid } = get(); if (wid) try { track((await xb.reenter(wid, rid, exp, params)).job); } catch (e) { set({ error: message(e) }); } },
    deleteRecord: async (rid) => {
      const { wid } = get();
      if (!wid) return;
      try { await xb.deleteRecord(wid, rid); if (get().record?.id === rid) set({ record: null }); if (get().compareWith?.id === rid) set({ compareWith: null }); await get().refreshHistory(); } catch (e) { set({ error: message(e) }); }
    },
    exportRecord: async (rid, fmt) => {
      const { wid } = get();
      if (!wid) return;
      try { saveText(`${rid}.${fmt}`, fmt === 'json' ? 'application/json' : 'text/csv', await xb.exportRecord(wid, rid, fmt)); } catch (e) { set({ error: message(e) }); }
    },
    exportHistory: async () => { const { wid } = get(); if (wid) try { saveText('xbtro-history.json', 'application/json', await xb.exportHistory(wid)); } catch (e) { set({ error: message(e) }); } },
    importText: async (text) => {
      const { wid } = get();
      if (!wid) return;
      try {
        const data = JSON.parse(text) as { schema?: string };
        if (data.schema === 'xbtro.history/1') { const r = await xb.importHistory(wid, data); set({ notice: `Imported ${r.imported} record(s).` }); } else { await xb.importRecord(wid, data); set({ notice: 'Imported the record.' }); }
        await get().refreshHistory();
      } catch (e) { set({ error: message(e) }); }
    },
    dismiss: () => set({ error: null, notice: null }),
  };
});
