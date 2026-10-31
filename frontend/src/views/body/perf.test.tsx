// Render-cost measurement under predefined conditions (small / medium / large series). Skipped unless TEOO_PERF=1 (it is a measurement, not a check). The figure is React renderToString of View B's plot in Node:
// the cost of one render pass of the component tree, NOT a browser frame rate (that is measured separately in a real browser).
import { writeFileSync } from 'node:fs';
import { renderToString } from 'react-dom/server';
import { describe, it } from 'vitest';
import type { TeooChannel } from './bodyApi';
import { Plot } from './views';

const sizes = { small: 1_000, medium: 5_000, large: 10_000 } as const;
const channel = (n: number): TeooChannel => {
  const times = Array.from({ length: n }, (_, i) => i / 50);
  const samples = times.map((t, i) => (i % 400 > 360 ? { value: null, status: 'MISSING', causes: ['SENSOR_DROPOUT'], cause_known: true, detection_limit: null, detail: null } : { value: 20 * Math.sin(t), status: 'MEASURED_VALID', causes: [], cause_known: true, detection_limit: null, detail: null }));
  return { variable: 'v', target: 't', unit: 'deg', times, samples, counts: {} };
};

describe.skipIf(!process.env.TEOO_PERF)('render cost of the plot', () => {
  it('measures renderToString of the plot per condition', () => {
    const out: Record<string, { samples: number; median_ms: number; p95_ms: number; html_kb: number; runs: number }> = {};
    for (const [name, n] of Object.entries(sizes)) {
      const ch = channel(n); renderToString(<Plot ch={ch} />); // warm up
      const ms: number[] = []; let len = 0;
      for (let i = 0; i < 30; i++) { const t0 = performance.now(); len = renderToString(<Plot ch={ch} />).length; ms.push(performance.now() - t0); }
      ms.sort((a, b) => a - b);
      out[name] = { samples: n, median_ms: Number(ms[15].toFixed(2)), p95_ms: Number(ms[28].toFixed(2)), html_kb: Math.round(len / 1024), runs: 30 };
    }
    writeFileSync(process.env.TEOO_PERF as string, JSON.stringify(out, null, 1));
  });
});
