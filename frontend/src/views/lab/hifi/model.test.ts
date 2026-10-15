import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { validate, type LabRecord } from '../labScene';
import { FLOOR_Y, PHYS, physToView, viewToPhys, type V3 } from './coords';
import { allEvents, inspect, levels, mediation, provenance, transfers, transitions } from './model';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..', '..');
const load = (n: string) => validate(JSON.parse(readFileSync(join(root, `backend/experiments/results/lab/${n}.json`), 'utf8')));
const SEP = load('m9-separated-resources-7000');
const EXT = load('m9-extinction-relocation-7000');
const fixture = (n: string) => JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'fixtures', `access-${n}.json`), 'utf8')) as
  { steps: { i: number; t: number; systems: Record<string, { coverage: string[]; accessible: string[] }> }[] };

describe('coordinates: rendered position = transform of the recorded physical position', () => {
  it('the transform is invertible and places a resting sample on its chamber floor', () => {
    const p: V3 = [12.3, -1.7, 0.2];
    expect(viewToPhys(physToView(p))).toEqual(p);
    expect(physToView([0, 0, 0.05 + PHYS.HALF])[1]).toBeCloseTo(FLOOR_Y + PHYS.HALF, 9);
  });
  it('every recorded sample at rest lies over a chamber floor or a port of the layout', () => {
    const L = SEP.layout!;
    const s = SEP.steps[0].physics!;
    for (const [sid, p] of Object.entries(s.samples)) {
      const v = physToView(p as V3);
      const onChamber = SEP.chambers.some((c) => Math.abs(v[0] - c.position[0]) <= L.chamber_half && Math.abs(v[2] - c.position[2]) <= L.chamber_half);
      const onPort = Object.values(L.ports).some(([x, y]) => Math.abs(v[0] - x) <= L.port_half && Math.abs(v[2] - y) <= L.port_half);
      expect(onChamber || onPort, sid).toBe(true);
    }
  });
});

describe('what a system can experimentally access equals the backend (science.py candidates) at every decision step', () => {
  for (const [name, rec] of [['m9-separated-resources-7000', SEP], ['m9-extinction-relocation-7000', EXT]] as [string, LabRecord][]) {
    it(name, () => {
      const fx = fixture(name);
      let compared = 0;
      for (const row of fx.steps) {
        for (const [sid, want] of Object.entries(row.systems)) {
          const got = levels(rec, row.i, sid)!;
          expect(got.observed, `${sid} t${row.t} coverage`).toEqual(want.coverage);
          expect([...got.accessible].sort(), `${sid} t${row.t} accessible`).toEqual(want.accessible);
          compared++;
        }
      }
      expect(compared).toBeGreaterThan(200);
    });
  }
});

describe('transport completion is not delivery', () => {
  it('a transfer is "delivered" only with a recorded material_delivered event; a blocked one stays "delivery blocked"', () => {
    const last = SEP.steps[SEP.steps.length - 1].t;
    const trs = transfers(SEP, last);
    const sc = SEP.science_events ?? [];
    expect(trs.filter((t) => t.state === 'delivered').length).toBe(sc.filter((e) => e.type === 'material_delivered').length);
    expect(trs.filter((t) => t.state === 'delivery blocked').length).toBe(sc.filter((e) => e.type === 'delivery_blocked').length);
    expect(sc.filter((e) => e.type === 'delivery_blocked').length).toBeGreaterThan(0);
    const complete = (SEP.physical_events ?? []).filter((e) => e.type === 'transfer_complete').length;
    expect(trs.filter((t) => ['delivered', 'delivery blocked', 'transport complete'].includes(t.state)).length).toBe(complete);
  });
});

describe('events, transitions and provenance reference recorded events', () => {
  it('event ids are unique and every recorded transition points to an existing event', () => {
    const ids = allEvents(SEP).map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const rec of [SEP, EXT]) {
      const known = new Set(allEvents(rec).map((e) => e.id));
      for (const tr of transitions(rec, Infinity)) {
        if (tr.eventId) expect(known.has(tr.eventId), tr.rule).toBe(true);
        if (!tr.eventId) expect(tr.derived).toBe(true);
      }
    }
  });
  it('extinction and re-ignition follow the M9-C definition and agree with the published confirmatory run', () => {
    const tr = transitions(EXT, Infinity);
    const m9c = JSON.parse(readFileSync(join(root, 'backend/experiments/results/lab9/m9c.json'), 'utf8'));
    const pub = m9c.per_run.find((x: { cond: string; i: number }) => x.cond === 'X6' && x.i === 0).systems.A;
    expect(tr.some((x) => x.kind === 'extinction')).toBe(pub.extinct === 1);
    const re = tr.find((x) => x.kind === 're-ignition');
    expect(re?.t ?? null).toBe(pub.reignited === 1 ? pub.reignition_step : null);
    expect(tr.filter((x) => x.kind === 'observation revision').length).toBeGreaterThan(0);
    expect(tr.filter((x) => x.kind === 'harness intervention').map((x) => x.rule)).toEqual(['declared harness intervention: close',
      'declared harness intervention: open']);
  });
  it('a delivery is traced back to the selection that initiated it, forward to its observation; no attribution is invented', () => {
    const id = allEvents(SEP).find((e) => e.type === 'material_delivered')!.id;
    const p = provenance(SEP, id)!;
    expect(p.initiating.map((e) => e.type)).toEqual(['experiment_selected']);
    expect(p.preceding.length).toBeGreaterThan(0);
    const cond = allEvents(SEP).find((e) => e.type === 'conduit_established')!;
    expect(provenance(SEP, cond.id)!.attribution).toMatch(/^recorded cause: /);
  });
});

describe('inspection shows recorded values or an availability status — never an invented value', () => {
  it('a chamber outside a system\'s coverage is reported as outside its observation range, not as zero', () => {
    const i = 300;
    const s = SEP.steps[i];
    const unseen = SEP.chambers.map((c) => c.cid).find((c) => !s.science!.B.coverage.includes(c))!;
    const f = inspect(SEP, i, { kind: 'chamber', id: unseen }).fields.find((x) => x.label === 'system B')!;
    expect(f.status).toBe('outside observation range');
  });
  it('private carriages say that per-system leg counts are unavailable rather than showing zero', () => {
    const f = inspect(SEP, 500, { kind: 'gantry', id: '0#a' }).fields.find((x) => x.label.startsWith('completed legs'))!;
    expect(f.status).toBe('measurement unavailable');
  });
  it('in the shared laboratory, mediation counts the legs each system had served on a gantry', () => {
    const m7 = load('m7-systems-6000');
    const med = mediation(m7, m7.steps.length - 1);
    expect(med.some((m) => m.shared)).toBe(true);
  });
});

describe('live and replay give the same model state for the same recorded state', () => {
  it('a record grown step by step (as the live viewer does) equals the replayed record at every compared step', () => {
    const rec = SEP;
    for (const k of [40, 200, 480, 959]) {
      const t = rec.steps[k].t;
      const live: LabRecord = { ...rec, steps: rec.steps.slice(0, k + 1), events: rec.events.filter((e) => e.t <= t),
        physical_events: (rec.physical_events ?? []).filter((e) => e.t <= t), science_events: (rec.science_events ?? []).filter((e) => e.t <= t) };
      for (const sid of ['A', 'B', 'C']) expect(levels(live, k, sid)).toEqual(levels(rec, k, sid));
      expect(transfers(live, t)).toEqual(transfers(rec, t));
      expect(mediation(live, k)).toEqual(mediation(rec, k));
      expect(transitions(live, t).filter((x) => x.kind !== 'extinction' && x.kind !== 're-ignition')).toEqual(
        transitions(rec, t).filter((x) => x.kind !== 'extinction' && x.kind !== 're-ignition'));
    }
  });
});
