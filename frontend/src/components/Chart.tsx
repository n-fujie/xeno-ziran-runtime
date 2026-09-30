// Minimal canvas line chart (no chart library): monochrome series, optional markers, click-to-pick a step.
import { useEffect, useRef } from 'react';

export interface Series { label: string; t: number[]; v: number[]; color?: string; dashed?: boolean }
export interface Marker { t: number; color: string; label?: string }

export default function Chart({ series, height = 120, markers = [], onPick, title, yLabel }: {
  series: Series[]; height?: number; markers?: Marker[]; onPick?: (t: number) => void; title?: string; yLabel?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const range = useRef<[number, number]>([0, 1]);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = cv.clientWidth;
      const h = height;
      cv.width = w * dpr;
      cv.height = h * dpr;
      const g = cv.getContext('2d')!;
      g.scale(dpr, dpr);
      g.clearRect(0, 0, w, h);
      const legendRow = series.length > 1;
      const pad = { l: 44, r: 8, t: (title ? 18 : 6) + (legendRow && title ? 12 : 0), b: 16 };
      let t0 = Infinity;
      let t1 = -Infinity;
      let v0 = Infinity;
      let v1 = -Infinity;
      for (const s of series) {
        for (let i = 0; i < s.t.length; i++) {
          t0 = Math.min(t0, s.t[i]); t1 = Math.max(t1, s.t[i]);
          const v = s.v[i];
          if (Number.isFinite(v)) { v0 = Math.min(v0, v); v1 = Math.max(v1, v); }
        }
      }
      if (!Number.isFinite(t0)) { t0 = 0; t1 = 1; v0 = 0; v1 = 1; }
      if (t1 === t0) t1 = t0 + 1;
      if (v1 === v0) { v1 = v0 + 1; }
      v0 = Math.min(v0, 0) === 0 && v0 >= 0 ? 0 : v0;
      range.current = [t0, t1];
      const X = (t: number) => pad.l + ((t - t0) / (t1 - t0)) * (w - pad.l - pad.r);
      const Y = (v: number) => h - pad.b - ((v - v0) / (v1 - v0)) * (h - pad.t - pad.b);
      g.font = '10px "IBM Plex Mono", Menlo, monospace';
      g.fillStyle = '#6b6b70';
      g.strokeStyle = '#1c1c20';
      g.lineWidth = 1;
      for (let k = 0; k <= 2; k++) {
        const v = v0 + ((v1 - v0) * k) / 2;
        const y = Y(v);
        g.beginPath(); g.moveTo(pad.l, y); g.lineTo(w - pad.r, y); g.stroke();
        g.fillText(fmt(v), 2, y + 3);
      }
      g.fillText(String(Math.round(t0)), pad.l, h - 3);
      g.fillText(String(Math.round(t1)), w - pad.r - 30, h - 3);
      if (title) { g.fillStyle = '#a8a8ad'; g.fillText(title + (yLabel ? `  (${yLabel})` : ''), pad.l, 11); }
      for (const m of markers) {
        if (m.t < t0 || m.t > t1) continue;
        g.strokeStyle = m.color; g.globalAlpha = 0.6;
        g.beginPath(); g.moveTo(X(m.t), pad.t); g.lineTo(X(m.t), h - pad.b); g.stroke();
        g.globalAlpha = 1;
      }
      for (const s of series) {
        g.strokeStyle = s.color ?? '#d8d8dc';
        g.lineWidth = 1.2;
        g.setLineDash(s.dashed ? [4, 3] : []);
        g.beginPath();
        let started = false;
        const stride = Math.max(1, Math.floor(s.t.length / (w * 1.5)));
        for (let i = 0; i < s.t.length; i += stride) {
          const v = s.v[i];
          if (!Number.isFinite(v)) continue;
          if (!started) { g.moveTo(X(s.t[i]), Y(v)); started = true; } else g.lineTo(X(s.t[i]), Y(v));
        }
        g.stroke();
      }
      g.setLineDash([]);
      if (series.length > 1) {
        let x = w - pad.r;
        for (const s of [...series].reverse()) {
          const tw = g.measureText(s.label).width;
          x -= tw + 18;
          g.fillStyle = s.color ?? '#d8d8dc';
          g.fillRect(x, title ? 20 : 5, 10, 2);
          g.fillStyle = '#a8a8ad';
          g.fillText(s.label, x + 13, title ? 25 : 10);
        }
      }
    };
    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(cv);
    return () => ro.disconnect();
  }, [series, height, markers, title, yLabel]);

  return (
    <canvas
      ref={ref}
      className="chart"
      style={{ height, cursor: onPick ? 'crosshair' : 'default' }}
      onClick={(e) => {
        if (!onPick) return;
        const r = (e.target as HTMLCanvasElement).getBoundingClientRect();
        const u = (e.clientX - r.left - 44) / (r.width - 52);
        const [t0, t1] = range.current;
        onPick(Math.round(t0 + Math.max(0, Math.min(1, u)) * (t1 - t0)));
      }}
    />
  );
}

function fmt(v: number): string {
  const a = Math.abs(v);
  if (a >= 1000) return (v / 1000).toFixed(1) + 'k';
  if (a >= 10) return v.toFixed(0);
  if (a >= 1) return v.toFixed(1);
  return v.toFixed(2);
}
