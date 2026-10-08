// One WebGL renderer for every spatial projection (network, shape space, address space, map, globe).
// Level of detail: cluster aggregates + flows at macro…local scales, viewport tiles of configurations at
// configuration/relation scales. Rendering reads the Mirror directly each animation frame; React only
// mounts/unmounts the Deck instance.

import {
  Deck, MapView, OrthographicView, _GlobeView as GlobeView,
  type Layer, type PickingInfo,
} from '@deck.gl/core';
import { ArcLayer, GeoJsonLayer, LineLayer, ScatterplotLayer, SolidPolygonLayer, TextLayer } from '@deck.gl/layers';
import { useEffect, useRef, useState } from 'react';
import { feature } from 'topojson-client';
import type { GeometryCollection, Topology } from 'topojson-specification';
import landTopo from 'world-atlas/land-110m.json';
import { api, type ClusterSummary, type CompareResult } from '../api/client';
import { TK, type Layout, type Mirror } from '../lod/mirror';
import { dequantize } from '../proto/decode';
import { useSim } from '../store/sim';
import { C, EDGE_CLASS_COLOR, FORMS, NODE_CLASS_COLOR } from './palette';
import { SCALE_NAMES } from './scales';

export type Projection = 'network' | 'shape' | 'address' | 'map' | 'globe';
const LAYOUT_OF: Record<Projection, Layout> = { network: 'network', shape: 'shape', address: 'address', map: 'geo', globe: 'geo' };
const BANDS = [0.7, 1.4, 2.1, 2.8, 3.9]; // zoom offsets above the base zoom at which the scale changes

const LAND = feature(landTopo as unknown as Topology, (landTopo as unknown as Topology).objects.land as GeometryCollection);
const WORLD_RING: [number, number][] = [[-180, -89], [180, -89], [180, 89], [-180, 89], [-180, -89]];

interface ViewState { target?: number[]; zoom: number; longitude?: number; latitude?: number; [k: string]: unknown }

interface LoadedTile { level: number; bounds: [number, number, number, number]; layoutVersion: number; nodes: Uint32Array }

function scaleFromZoom(zoom: number, base: number): number {
  const d = zoom - base;
  let s = 0;
  while (s < BANDS.length && d >= BANDS[s]) s++;
  return s;
}

function zoomForScale(s: number, base: number): number {
  const lo = s === 0 ? -0.3 : BANDS[s - 1];
  const hi = s < BANDS.length ? BANDS[s] : BANDS[BANDS.length - 1] + 1.2;
  return base + (lo + hi) / 2;
}

export default function GraphView({ projection, compare, onClusterHover }: {
  projection: Projection; compare?: CompareResult | null; onClusterHover?: (a: string | null) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [hud, setHud] = useState({ nodes: 0, edges: 0, particles: 0, truncated: false, loading: false });
  const info = useSim((s) => s.info);
  const mirrorState = useSim((s) => s.mirror);

  useEffect(() => {
    if (!host.current || !info || !mirrorState) return;
    const mirror: Mirror = mirrorState;
    const sid = info.id;
    const layout = LAYOUT_OF[projection];
    const geo = projection === 'map' || projection === 'globe';
    const el = host.current;
    const w = el.clientWidth || 800;
    const h = el.clientHeight || 600;
    const fitZoom = geo ? (projection === 'globe' ? 1.4 : 1.1) : Math.log2(Math.min(w, h) / 1080);
    // Shape Space opens at the Configuration scale: its points are the object of interest there
    const baseZoom = projection === 'shape' ? fitZoom - zoomForScale(4, 0) : fitZoom;
    let viewState: ViewState = geo
      ? { longitude: 10, latitude: 18, zoom: fitZoom, pitch: 0, bearing: 0 }
      : { target: [500, 500, 0], zoom: fitZoom, minZoom: baseZoom - 1.5, maxZoom: baseZoom + 7 };
    const view = projection === 'globe' ? new GlobeView({ id: 'v', controller: true })
      : projection === 'map' ? new MapView({ id: 'v', controller: true, repeat: false })
        : new OrthographicView({ id: 'v', controller: true });

    let clusters: ClusterSummary | null = null;
    let clusterLevel = -1;
    let clusterFetchWall = 0;
    let clusterLayoutVersion = -1;
    let tile: LoadedTile | null = null;
    let centered = false;
    let tilePending = false;
    let tileWall = 0;
    let tileTimer = 0;
    let edgeCache: { version: number; pv: number; key: string; src: Float32Array; dst: Float32Array; col: Uint8Array; n: number } | null = null;
    let prevPositions: Float32Array | null = null;
    let transitionStart = 0;
    let destroyed = false;
    let frames = 0;
    let fpsWall = performance.now();
    let hudWall = 0;
    let lastScale = -1;
    let selectedDetail: { id: number; to: number[] } | null = null;
    const pos = () => mirror.positions[layout];

    const deck = new Deck({
      parent: el,
      views: view,
      viewState: viewState as never, // controlled: we own the camera; deck reports changes and interpolates transitions
      controller: true,
      style: { background: 'transparent' },
      onViewStateChange: ({ viewState: vs }) => {
        anim = null; // user interaction takes over
        viewState = vs as ViewState;
        deck.setProps({ viewState: vs as never });
        scheduleTile();
        return vs;
      },
      getTooltip: (pi: PickingInfo) => tooltip(pi),
      onClick: (pi: PickingInfo) => click(pi),
      onHover: (pi: PickingInfo) => {
        if (pi.layer?.id === 'clusters' && clusters) onClusterHover?.(clusters.addresses[pi.index] ?? null);
        else onClusterHover?.(null);
      },
      getCursor: ({ isHovering, isDragging }) => (isDragging ? 'grabbing' : isHovering ? 'pointer' : 'grab'),
      layers: [],
    });

    const currentScale = () => scaleFromZoom(viewState.zoom, baseZoom);

    function bounds(): [number, number, number, number] {
      if (projection === 'globe') return [-180, -90, 180, 90];
      const vp = deck.getViewports()[0];
      if (!vp) return [0, 0, 1000, 1000];
      const b = vp.getBounds();
      const pad = [(b[2] - b[0]) * 0.3, (b[3] - b[1]) * 0.3];
      const out: [number, number, number, number] = [b[0] - pad[0], b[1] - pad[1], b[2] + pad[0], b[3] + pad[1]];
      if (geo) return [Math.max(-180, out[0]), Math.max(-90, out[1]), Math.min(180, out[2]), Math.min(90, out[3])];
      return out;
    }

    function scheduleTile() {
      window.clearTimeout(tileTimer);
      tileTimer = window.setTimeout(maybeLoadTile, 140);
    }

    async function maybeLoadTile(force = false) {
      const s = currentScale();
      useSim.getState().setScale(s);
      if (s < 4 || tilePending || destroyed) return;
      const level = s === 5 ? 5 : 4;
      const b = bounds();
      const lv = useSim.getState().status?.layout_version ?? 0;
      const inside = tile && tile.level === level && b[0] >= tile.bounds[0] && b[1] >= tile.bounds[1] &&
        b[2] <= tile.bounds[2] && b[3] <= tile.bounds[3] &&
        (layout !== 'shape' || tile.layoutVersion === lv || performance.now() - tileWall < 2000);
      if (inside && !force) return;
      tilePending = true;
      setHud((x) => ({ ...x, loading: true }));
      try {
        const t = await api.tile(sid, layout, level, b, layout === 'shape' && level === 4 ? 0 : 20000);
        if (destroyed) return;
        if (layout === 'shape' && tile) {
          prevPositions = pos().slice();
          transitionStart = performance.now();
        }
        mirror.applyTile(layout, t);
        tile = { level, bounds: b, layoutVersion: lv, nodes: t.nodes };
        tileWall = performance.now();
        setHud((x) => ({ ...x, truncated: t.truncated && !(layout === 'shape' && level === 4), loading: false }));
      } catch {
        setHud((x) => ({ ...x, loading: false }));
      } finally {
        tilePending = false;
      }
    }

    async function maybeLoadClusters() {
      const s = currentScale();
      if (s > 3) return;
      const lv = useSim.getState().status?.layout_version ?? 0;
      const now = performance.now();
      const stale = now - clusterFetchWall > 3000 || (layout === 'shape' && lv !== clusterLayoutVersion && now - clusterFetchWall > 2000);
      if (clusterLevel === s && !stale) return;
      clusterFetchWall = now;
      clusterLevel = s;
      clusterLayoutVersion = lv;
      const ws = useSim.getState().ws;
      if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'view', level: s }));
      try {
        const c = await api.clusters(sid, s);
        if (!destroyed && c.level === currentScale()) {
          clusters = c;
          if (geo && !centered) {
            centered = true;
            const pts = c.centroids.geo.filter((p) => p[0] !== null && p[1] !== null) as number[][];
            if (pts.length) {
              const lon = pts.reduce((a, p) => a + p[0], 0) / pts.length;
              const lat = pts.reduce((a, p) => a + p[1], 0) / pts.length;
              flyTo([lon, lat], viewState.zoom);
            }
          }
        }
      } catch { /* retried on next tick */ }
    }

    function nodeXY(i: number, out: number[], k: number): boolean {
      const p = pos();
      let x = p[2 * i];
      let y = p[2 * i + 1];
      if (Number.isNaN(x)) return false;
      if (prevPositions && k < 1) {
        const px = prevPositions[2 * i];
        const py = prevPositions[2 * i + 1];
        if (!Number.isNaN(px)) {
          x = px + (x - px) * k;
          y = py + (y - py) * k;
        }
      }
      out[0] = x;
      out[1] = y;
      return true;
    }

    // ------------------------------------------------------------------ layer builders
    function clusterLayers(now: number, cmp: CompareResult | null | undefined): Layer[] {
      if (!clusters) return [];
      const c = clusters;
      const cent = c.centroids[layout];
      const agg = mirror.aggregates && mirror.aggregates.level === c.level ? mirror.aggregates : null;
      const maxCount = Math.max(...c.count);
      const idx = c.addresses.map((_, i) => i).filter((i) => cent[i][0] !== null);
      const radiusBase = [17, 11, 7, 4][c.level] ?? 4;
      const pulseK = Math.exp(-(now - mirror.aggregateWall) / 260);
      const changed = cmp && useSim.getState().compareOverlay ? cmp.cluster_changes?.[c.level] ?? null : null;
      const layers: Layer[] = [];
      const flows = c.flows.filter((f) => cent[f[0]][0] !== null && cent[f[1]][0] !== null).slice(0, [60, 160, 260, 360][c.level]);
      const maxW = Math.max(1e-9, ...flows.map((f) => f[3]));
      const maxL = Math.max(1e-9, ...flows.map((f) => f[4]));
      const flowProps = {
        id: 'flows', data: flows,
        getSourcePosition: (f: number[]) => cent[f[0]] as [number, number],
        getTargetPosition: (f: number[]) => cent[f[1]] as [number, number],
        getWidth: (f: number[]) => 0.4 + (c.level >= 2 ? 1.6 : 3.2) * Math.sqrt(f[3] / maxW),
        getColor: (f: number[]) => [220, 220, 225, Math.round((c.level >= 2 ? 12 : 25) + (c.level >= 2 ? 90 : 150) * Math.sqrt(f[4] / maxL))] as [number, number, number, number],
        widthUnits: 'pixels' as const,
        updateTriggers: { getColor: c, getWidth: c },
      };
      layers.push(geo ? new ArcLayer({ ...flowProps, greatCircle: true, getHeight: 0.15,
        getSourceColor: flowProps.getColor, getTargetColor: flowProps.getColor })
        : new LineLayer(flowProps));
      const spread = c.spread?.[layout] ?? [];
      const activity = (i: number) => {
        const act = agg ? agg.ignitions[i] / Math.max(1, c.count[i]) : 0;
        const md = agg ? agg.meanDiff[i] : 0;
        const prev = mirror.aggregatePrev?.[i] ?? 0;
        const rise = agg && agg.ignitions[i] > prev ? pulseK : 0;
        return Math.min(1, 1.6 * act + 0.12 * md + 0.35 * rise);
      };
      // extent: translucent disc of the members' RMS spread (world units) — the aggregate is where its members are
      layers.push(new ScatterplotLayer({
        id: 'cluster-extent', data: c.level <= 1 && projection !== 'globe' ? idx.filter((i) => spread[i]) : [],
        getPosition: (i: number) => cent[i] as [number, number],
        getRadius: (i: number) => (spread[i] ?? 0) * (geo ? 111_000 : 1),
        radiusUnits: geo ? 'meters' : 'common', stroked: true, lineWidthUnits: 'pixels', getLineWidth: 0.6,
        getFillColor: (i: number) => { const a = activity(i); return [255, 255, 255, Math.round(4 + 26 * a)]; },
        getLineColor: [120, 120, 128, 70],
        updateTriggers: { getFillColor: now },
      }));
      layers.push(new ScatterplotLayer({
        id: 'clusters', data: idx, pickable: true,
        getPosition: (i: number) => cent[i] as [number, number],
        getRadius: (i: number) => radiusBase * (0.35 + 0.65 * Math.sqrt(c.count[i] / maxCount)),
        radiusUnits: 'pixels', stroked: true, lineWidthUnits: 'pixels', getLineWidth: 1,
        getFillColor: (i: number) => {
          const v = Math.round(22 + 233 * activity(i));
          return [v, v, v, 235];
        },
        getLineColor: (i: number) => changed && changed[i] > 0.02
          ? [255, 190, 90, Math.round(80 + 175 * Math.min(1, changed[i] * 4))] : [150, 150, 155, 120],
        updateTriggers: { getFillColor: now, getLineColor: [changed, now] },
      }));
      if (c.level <= 1) {
        layers.push(new TextLayer({
          id: 'cluster-labels', data: idx, getPosition: (i: number) => cent[i] as [number, number],
          getText: (i: number) => c.addresses[i], getSize: c.level === 0 ? 13 : 10, getColor: [160, 160, 165, 200],
          getPixelOffset: [0, -radiusBase - 8], fontFamily: 'IBM Plex Mono, Menlo, monospace',
          characterSet: '0123456789.', updateTriggers: { getPosition: c },
        }));
      }
      return layers;
    }

    function edgeBuffers(scale: number, cmp: CompareResult | null | undefined, k: number) {
      const key = `${scale}|${cmp?.id ?? ''}|${k < 1 ? performance.now() : 'settled'}`;
      if (edgeCache && edgeCache.version === mirror.edgesVersion && edgeCache.pv === mirror.positionsVersion && edgeCache.key === key) {
        return edgeCache;
      }
      const m = mirror.edgeSrc.size;
      const src = new Float32Array(m * 2);
      const dst = new Float32Array(m * 2);
      const col = new Uint8Array(m * 4);
      const a = [0, 0];
      const b = [0, 0];
      let n = 0;
      for (const [e, s] of mirror.edgeSrc) {
        const d = mirror.edgeDst.get(e)!;
        if (!nodeXY(s, a, k) || !nodeXY(d, b, k)) continue;
        src[2 * n] = a[0]; src[2 * n + 1] = a[1];
        dst[2 * n] = b[0]; dst[2 * n + 1] = b[1];
        const wv = mirror.edgeW.get(e) ?? 0.5;
        const g = mirror.edgeGate.get(e) ?? 1;
        const tr = mirror.edgeTransform.get(e) ?? 0;
        const base = g < 0.999 ? C.gated : tr && scale === 5 ? C.transformEdge : C.edge;
        const alpha = Math.round((scale === 5 ? 50 : 22) + (scale === 5 ? 150 : 90) * Math.min(1, (wv * Math.max(g, 0.15)) / 1.4));
        col.set([base[0], base[1], base[2], alpha], 4 * n);
        n++;
      }
      edgeCache = { version: mirror.edgesVersion, pv: mirror.positionsVersion, key, src, dst, col, n };
      return edgeCache;
    }

    function nodeLayers(now: number, scale: number, cmp: CompareResult | null | undefined): Layer[] {
      const layers: Layer[] = [];
      const k = prevPositions ? Math.min(1, (now - transitionStart) / 700) : 1;
      if (k >= 1) prevPositions = null;
      const eb = edgeBuffers(scale, cmp, k);
      if (!(layout === 'shape' && scale === 4)) layers.push(new LineLayer({
        id: 'edges', data: { length: eb.n, attributes: {
          getSourcePosition: { value: eb.src, size: 2 }, getTargetPosition: { value: eb.dst, size: 2 },
          getColor: { value: eb.col, size: 4, normalized: true } } },
        getWidth: scale === 5 ? 1.2 : 0.7, widthUnits: 'pixels',
      }));
      const nodes = tile?.nodes ?? new Uint32Array(0);
      const vis: number[] = [];
      const xy = new Float32Array(nodes.length * 2);
      const fill = new Uint8Array(nodes.length * 4);
      const rad = new Float32Array(nodes.length);
      const ring = new Uint8Array(nodes.length * 4);
      const ringR = new Float32Array(nodes.length);
      const q = info!.quant_max;
      const p = [0, 0];
      let n = 0;
      for (let j = 0; j < nodes.length; j++) {
        const i = nodes[j];
        if (!nodeXY(i, p, k)) continue;
        vis.push(i);
        xy[2 * n] = p[0]; xy[2 * n + 1] = p[1];
        const diff = dequantize(mirror.diffQ[i], q);
        const te = mirror.thetaEff[i] || 1;
        const near = Math.min(1, diff / te);
        const pulse = Math.exp(-(now - mirror.igniteWall[i]) / 170);
        const frozen = mirror.frozen[i] === 1;
        let v = 34 + 150 * near;
        v = v + (255 - v) * pulse;
        if (frozen) fill.set([C.frozen[0] * 0.5, C.frozen[1] * 0.5, C.frozen[2] * 0.6, 220], 4 * n);
        else if (scale === 5) {
          const f = FORMS[mirror.form[i] % FORMS.length];
          const s = v / 255;
          fill.set([f[0] * s + 255 * pulse * (1 - s), f[1] * s + 255 * pulse * (1 - s), f[2] * s + 255 * pulse * (1 - s), 240], 4 * n);
        } else fill.set([v, v, v, 235], 4 * n);
        const r0 = scale === 5 ? 4.2 : 2.6;
        rad[n] = scale === 5 ? r0 * (0.45 + 0.55 * near) + 3 * pulse : r0 + 2.2 * pulse;
        // memory afterimage (and, at relation scale, the threshold ring)
        const mem = mirror.memQ[i];
        ring.set(scale === 5 ? [190, 190, 200, Math.min(255, 50 + mem)] : [200, 200, 210, Math.min(160, mem * 0.8)], 4 * n);
        ringR[n] = scale === 5 ? r0 + 2.5 + 3 * (mem / 255) : r0 + 1.5 + 3 * (mem / 255);
        n++;
      }
      layers.push(new ScatterplotLayer({
        id: 'memory', data: { length: n, attributes: {
          getPosition: { value: xy, size: 2 }, getRadius: { value: ringR, size: 1 },
          getLineColor: { value: ring, size: 4, normalized: true } } },
        stroked: true, filled: false, radiusUnits: 'pixels', lineWidthUnits: 'pixels', getLineWidth: scale === 5 ? 1 : 0.6,
      }));
      layers.push(new ScatterplotLayer({
        id: 'nodes', pickable: true, data: { length: n, attributes: {
          getPosition: { value: xy, size: 2 }, getRadius: { value: rad, size: 1 },
          getFillColor: { value: fill, size: 4, normalized: true } } },
        radiusUnits: 'pixels', radiusMinPixels: 0.8,
      }));
      visibleNodes = vis;
      // compare overlay
      if (cmp && useSim.getState().compareOverlay) {
        const cn: number[] = [];
        for (const i of vis) if (cmp.node_classes[i]) cn.push(i);
        layers.push(new ScatterplotLayer({
          id: 'compare-nodes', data: cn, getPosition: (i: number) => (nodeXY(i, p, 1) ? [p[0], p[1]] : [0, 0]),
          getRadius: scale === 5 ? 8 : 4.5, radiusUnits: 'pixels', stroked: true, filled: false,
          lineWidthUnits: 'pixels', getLineWidth: 1.4,
          getLineColor: (i: number) => [...NODE_CLASS_COLOR[cmp.node_classes[i]], 230] as [number, number, number, number],
          updateTriggers: { getPosition: [mirror.positionsVersion], getLineColor: cmp },
        }));
        const ce = cmp.edges.filter(([a, b]) => !Number.isNaN(pos()[2 * a]) && !Number.isNaN(pos()[2 * b]));
        layers.push(new LineLayer({
          id: 'compare-edges', data: ce,
          getSourcePosition: (e: number[]) => [pos()[2 * e[0]], pos()[2 * e[0] + 1]],
          getTargetPosition: (e: number[]) => [pos()[2 * e[1]], pos()[2 * e[1] + 1]],
          getColor: (e: number[]) => [...EDGE_CLASS_COLOR[e[2]], 200] as [number, number, number, number],
          getWidth: 1.6, widthUnits: 'pixels', updateTriggers: { getSourcePosition: mirror.positionsVersion },
        }));
      }
      return layers;
    }

    let visibleNodes: number[] = [];

    function transientLayers(now: number, scale: number): Layer[] {
      const tr = mirror.transients;
      const parts: number[] = [];
      const partCol: number[] = [];
      const segs: number[] = [];
      const segCol: number[] = [];
      const rings: number[] = [];
      const ringCol: number[] = [];
      const ringR: number[] = [];
      const a = [0, 0];
      const b = [0, 0];
      const maxParticles = scale === 5 ? 6000 : 3500;
      let np = 0;
      for (let x = tr.length - 1; x >= 0; x--) {
        const t = tr[x];
        const age = now - t.wall;
        if (age < 0) continue;
        if (age > 900) break;
        if (!nodeXY(t.a, a, 1)) continue;
        if (t.kind === TK.PENETRATE) {
          if (age > 420 || np >= maxParticles || !nodeXY(t.b, b, 1)) continue;
          const u = age / 420;
          parts.push(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u);
          partCol.push(C.penetration[0], C.penetration[1], C.penetration[2], Math.round(235 * (1 - u * 0.6)));
          np++;
        } else if (t.kind === TK.CUT) {
          if (age > 800 || !nodeXY(t.b, b, 1)) continue;
          const u = age / 800;
          const mx = (a[0] + b[0]) / 2;
          const my = (a[1] + b[1]) / 2;
          const al = Math.round(255 * (1 - u));
          // the connection visibly breaks: two halves retracting from the middle
          segs.push(a[0], a[1], mx + (a[0] - mx) * u, my + (a[1] - my) * u);
          segs.push(b[0], b[1], mx + (b[0] - mx) * u, my + (b[1] - my) * u);
          segCol.push(...C.cut, al, ...C.cut, al);
        } else if (t.kind === TK.NEW || t.kind === TK.RECONF_NEW) {
          if (age > 900 || !nodeXY(t.b, b, 1)) continue;
          const u = Math.min(1, age / 450);
          const colr = t.kind === TK.NEW ? C.newConn : C.reconf;
          segs.push(a[0], a[1], a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u);
          segCol.push(...colr, Math.round(255 * (1 - Math.max(0, age - 450) / 450)));
        } else if (t.kind === TK.RECONF_OLD) {
          if (age > 700 || !nodeXY(t.b, b, 1)) continue;
          segs.push(a[0], a[1], b[0], b[1]);
          segCol.push(...C.reconf, Math.round(120 * (1 - age / 700)));
        } else if (t.kind === TK.RETURN) {
          const u = age / 900;
          rings.push(a[0], a[1]);
          ringR.push(3 + 16 * u);
          ringCol.push(...C.ret, Math.round(255 * (1 - u)));
        } else if (t.kind === TK.BRANCH && scale >= 4) {
          if (age > 500) continue;
          rings.push(a[0], a[1]);
          ringR.push(2 + 5 * (age / 500));
          ringCol.push(255, 255, 255, Math.round(150 * (1 - age / 500)));
        }
      }
      const layers: Layer[] = [];
      if (segs.length) {
        const s = new Float32Array(segs);
        const src = new Float32Array(s.length / 2);
        const dst = new Float32Array(s.length / 2);
        for (let i = 0; i < s.length / 4; i++) {
          src[2 * i] = s[4 * i]; src[2 * i + 1] = s[4 * i + 1];
          dst[2 * i] = s[4 * i + 2]; dst[2 * i + 1] = s[4 * i + 3];
        }
        layers.push(new LineLayer({ id: 'transient-segments', data: { length: src.length / 2, attributes: {
          getSourcePosition: { value: src, size: 2 }, getTargetPosition: { value: dst, size: 2 },
          getColor: { value: new Uint8Array(segCol), size: 4, normalized: true } } },
        getWidth: 2, widthUnits: 'pixels' }));
      }
      if (rings.length) {
        layers.push(new ScatterplotLayer({ id: 'transient-rings', data: { length: rings.length / 2, attributes: {
          getPosition: { value: new Float32Array(rings), size: 2 }, getRadius: { value: new Float32Array(ringR), size: 1 },
          getLineColor: { value: new Uint8Array(ringCol), size: 4, normalized: true } } },
        stroked: true, filled: false, radiusUnits: 'pixels', lineWidthUnits: 'pixels', getLineWidth: 1.3 }));
      }
      if (parts.length) {
        layers.push(new ScatterplotLayer({ id: 'particles', data: { length: parts.length / 2, attributes: {
          getPosition: { value: new Float32Array(parts), size: 2 },
          getFillColor: { value: new Uint8Array(partCol), size: 4, normalized: true } } },
        getRadius: scale === 5 ? 2.2 : 1.4, radiusUnits: 'pixels' }));
      }
      particleCount = np;
      return layers;
    }
    let particleCount = 0;

    function selectionLayers(): Layer[] {
      const sel = useSim.getState().selected;
      if (sel === null) return [];
      const p = [0, 0];
      if (!nodeXY(sel, p, 1)) return [];
      const layers: Layer[] = [new ScatterplotLayer({ id: 'selected', data: [sel], getPosition: () => [p[0], p[1]],
        getRadius: 11, radiusUnits: 'pixels', stroked: true, filled: false, lineWidthUnits: 'pixels', getLineWidth: 1.5,
        getLineColor: [...C.selected, 255], updateTriggers: { getPosition: [p[0], p[1]] } })];
      if (selectedDetail && selectedDetail.id === sel) {
        const q = [0, 0];
        const seg = selectedDetail.to.filter((t) => nodeXY(t, q, 1)).map((t) => {
          nodeXY(t, q, 1);
          return [p[0], p[1], q[0], q[1]];
        });
        layers.push(new LineLayer({ id: 'selected-out', data: seg, getSourcePosition: (s: number[]) => [s[0], s[1]],
          getTargetPosition: (s: number[]) => [s[2], s[3]], getColor: [255, 255, 255, 200], getWidth: 1.4,
          widthUnits: 'pixels' }));
      }
      return layers;
    }

    function backgroundLayers(): Layer[] {
      if (!geo) return [];
      const layers: Layer[] = [];
      if (projection === 'globe') {
        layers.push(new SolidPolygonLayer({ id: 'sphere', data: [WORLD_RING], getPolygon: (d: [number, number][]) => d,
          getFillColor: [6, 6, 8, 255] }));
      }
      layers.push(new GeoJsonLayer({ id: 'land', data: LAND, stroked: true, filled: true, getFillColor: C.land,
        getLineColor: C.landLine, lineWidthUnits: 'pixels', getLineWidth: 0.6 }));
      return layers;
    }

    function tooltip(pi: PickingInfo): { text: string } | null {
      if (pi.layer?.id === 'clusters' && clusters && pi.index >= 0) {
        const s = clusters.level;
        return { text: `${SCALE_NAMES[s]} cluster ${clusters.addresses[pi.index]}\n${clusters.count[pi.index]} configurations` };
      }
      if (pi.layer?.id === 'nodes' && pi.index >= 0) {
        const i = visibleNodes[pi.index];
        const d = dequantize(mirror.diffQ[i], info!.quant_max);
        return { text: `c${i}\ndifference ${d.toFixed(2)} / θ ${mirror.thetaEff[i].toFixed(2)}` };
      }
      return null;
    }

    function click(pi: PickingInfo) {
      if (pi.layer?.id === 'nodes' && pi.index >= 0) {
        const i = visibleNodes[pi.index];
        useSim.getState().select(i);
        void api.node(sid, i).then((nd) => {
          selectedDetail = { id: i, to: nd.reachable_transitions.filter((r) => r.reachable).map((r) => r.to) };
        });
        return;
      }
      if (pi.layer?.id === 'clusters' && clusters && pi.coordinate) {
        const s = Math.min(5, clusters.level + 1);
        flyTo(pi.coordinate as number[], zoomForScale(s, baseZoom));
      }
    }

    // camera animation is done here (not by deck transitions), so successive requests always apply
    let anim: { from: ViewState; to: ViewState; t0: number; dur: number } | null = null;
    function flyTo(center: number[], zoom: number) {
      const to: ViewState = geo ? { ...viewState, longitude: center[0], latitude: center[1], zoom }
        : { ...viewState, target: [center[0], center[1], 0], zoom };
      anim = { from: { ...viewState }, to, t0: performance.now(), dur: geo ? 800 : 600 };
    }
    function stepAnimation(now: number) {
      if (!anim) return;
      const u = Math.min(1, (now - anim.t0) / anim.dur);
      const e = u < 0.5 ? 2 * u * u : 1 - (-2 * u + 2) ** 2 / 2;
      const lerp = (a: number, b: number) => a + (b - a) * e;
      const { from, to } = anim;
      const vs: ViewState = { ...to, zoom: lerp(from.zoom, to.zoom) };
      if (geo) {
        vs.longitude = lerp(from.longitude ?? 0, to.longitude ?? 0);
        vs.latitude = lerp(from.latitude ?? 0, to.latitude ?? 0);
      } else {
        const a = from.target ?? [500, 500, 0];
        const b = to.target ?? [500, 500, 0];
        vs.target = [lerp(a[0], b[0]), lerp(a[1], b[1]), 0];
      }
      viewState = vs;
      deck.setProps({ viewState: vs as never });
      if (u >= 1) {
        anim = null;
        void maybeLoadTile();
      }
    }

    // external scale requests (breadcrumb)
    const unsub = useSim.subscribe((s, prev) => {
      if (s.requestedScale !== null && s.requestedScale !== prev.requestedScale) {
        let center = geo ? [viewState.longitude ?? 0, viewState.latitude ?? 0] : (viewState.target ?? [500, 500]);
        // drilling down: go to the populated cluster nearest to the current centre
        if (s.requestedScale > currentScale() && clusters) {
          const cent = clusters.centroids[layout];
          let best = -1;
          let bd = Infinity;
          cent.forEach((c, k) => {
            if (c[0] === null || c[1] === null) return;
            const d = (c[0] - center[0]) ** 2 + (c[1] - center[1]) ** 2 - clusters!.count[k] * 1e-3;
            if (d < bd) { bd = d; best = k; }
          });
          if (best >= 0) center = cent[best] as number[];
        }
        flyTo(center, zoomForScale(s.requestedScale, baseZoom));
        useSim.getState().requestScale(null);
      }
      if (s.resyncTick !== prev.resyncTick) {
        tile = null;
        void maybeLoadTile(true);
      }
      if (s.layoutTick !== prev.layoutTick && layout === 'shape') scheduleTile(); // rate-limited in maybeLoadTile
    });

    // ------------------------------------------------------------------ frame loop
    let raf = 0;
    const frame = () => {
      if (destroyed) return;
      const now = performance.now();
      stepAnimation(now);
      const scale = currentScale();
      if (scale !== lastScale) {
        lastScale = scale;
        useSim.getState().setScale(scale);
        if (scale >= 4) void maybeLoadTile(true);
      }
      if (scale <= 3) void maybeLoadClusters();
      const cmp = compare ?? (useSim.getState().compareOverlay ? useSim.getState().compare : null);
      const layers: Layer[] = [...backgroundLayers()];
      if (scale <= 3) layers.push(...clusterLayers(now, cmp));
      else layers.push(...nodeLayers(now, scale, cmp));
      if (scale >= 4) layers.push(...transientLayers(now, scale), ...selectionLayers());
      else particleCount = 0;
      deck.setProps({ layers });
      frames++;
      if (now - fpsWall >= 1000) {
        useSim.getState().setFps(Math.round((frames * 1000) / (now - fpsWall)));
        frames = 0;
        fpsWall = now;
      }
      if (now - hudWall > 400) {
        hudWall = now;
        setHud((x) => ({ ...x, nodes: scale >= 4 ? visibleNodes.length : clusters?.addresses.length ?? 0,
          edges: scale >= 4 ? (layout === 'shape' && scale === 4 ? 0 : edgeCache?.n ?? 0) : clusters?.flows.length ?? 0,
          particles: particleCount }));
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    void maybeLoadClusters();

    return () => {
      destroyed = true;
      cancelAnimationFrame(raf);
      window.clearTimeout(tileTimer);
      unsub();
      deck.finalize();
    };
  }, [projection, info, mirrorState, compare, onClusterHover]);

  const scale = useSim((s) => s.scale);
  const noGeo = info ? info.n - info.geo_count : 0;
  return (
    <div className="graph">
      <div ref={host} className="graph-canvas" />
      <div className="graph-hud mono">
        <span>{SCALE_NAMES[scale]}</span>
        <span>{scale >= 4 ? `${hud.nodes.toLocaleString()} configurations · ${hud.edges.toLocaleString()} connections`
          : `${hud.nodes} clusters · ${hud.edges} aggregated flows`}</span>
        {hud.particles > 0 && <span>{hud.particles} propagating</span>}
        {hud.truncated && <span className="warn">connections capped for this viewport</span>}
        {hud.loading && <span className="dim">loading…</span>}
        {(projection === 'map' || projection === 'globe') && noGeo > 0 &&
          <span className="dim">{noGeo.toLocaleString()} configurations have no geo projection (present in other views)</span>}
      </div>
    </div>
  );
}
