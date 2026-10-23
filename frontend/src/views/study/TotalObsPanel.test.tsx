/* eslint-disable @typescript-eslint/no-explicit-any */
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import run from './__fixtures__/totalobs_run.json';
import { Conditions, Trace } from './TotalObsPanel';

// A contract test: the panel reads the shape of a real run record written by the backend (a stored 5-generation run with a sensor failure at generation 2).
const rec: any = run;

describe('TotalObsPanel reads the stored run record', () => {
  const html = renderToString(<Trace rec={rec} />).replace(/<!-- -->/g, '');
  it('shows one row per generation with its question and reachability verdict', () => {
    expect(rec.totalobs.generations).toHaveLength(5);
    for (const g of rec.totalobs.generations) {
      expect(html).toContain(`${g.before.question}→${g.decision.question_next}`);
      expect(html).toContain(g.levels.dynamic_effect);
    }
  });
  it('shows the failure that the harness applied and the generation it appears in', () => {
    expect(rec.totalobs.generations[2].trigger.events.map((e: any) => e.do)).toContain('fail_sensor');
    expect(rec.totalobs.generations[2].failure.expired).toContain('S0');
  });
  it('keeps the eight ontological layers and says which reader each belongs to', () => {
    for (const layer of ['object_transitions', 'observer_transitions', 'interaction', 'interventions', 'recording', 'residual_consequences', 'agent_access', 'constructions']) {
      expect(html).toContain(layer);
    }
    expect(html).toContain('not reality as a whole');
    expect(rec.totalobs.scope_audit).toEqual([]);
  });
  it('lists the metric definitions with their versions', () => {
    for (const m of Object.keys(rec.totalobs.metric_log.registry)) expect(html).toContain(m);
  });
});

describe('planetary conditions', () => {
  it('state that the model is synthetic and make no claim about the Earth', () => {
    const html = renderToString(<Conditions c={rec.totalobs.planetary} />).replace(/<!-- -->/g, '');
    expect(html).toContain('earth_claim: false');
    expect(rec.totalobs.planetary.earth_claim).toBe(false);
    expect(html).toContain('propagation time');
    expect(html).toContain('not met');  // an unmet condition is labelled as such, not with a status word that means something else in this app
  });
});
