// XENO ECOSYSTEM, fifth stage — a deep link restores the state it describes: parse, format and plan are inverse where they should be, and the same link always gives the same plan.
import { describe, expect, it } from 'vitest';
import { FULL_OBSERVATION } from './meosApi';
import { deepLinkPlan, formatDeepLink, formatObs, parseDeepLink, parseObs, type DeepLink } from './deeplink';

const FULL: DeepLink = {
  seed: 7, tick: 165, mfs: 'MFS-F14-2', experiment: 'F14', sssmap: 'MFS-F14-1', sss: [1.2, 1, 0.9], address: { mode: 'reassign', tick: 100, target: 'A2', x: 11, y: 6 },
  obs: { sampling_interval: 3, spatial_stride: 2, region: [2, 4, 6, 8], occluder: [3, 5, 5, 7], threshold: 0.1, window: 24, address_resolution: 0.9 }, layers: ['route.fallback', 'mfs.current', 'mfs.rejected'], routelayers: ['active', 'failed'], cam: 'body', quality: 'balanced',
};

describe('deep links', () => {
  it('round-trips a full state through a URL', () => {
    const url = formatDeepLink(FULL);
    expect(parseDeepLink(url)).toEqual(FULL);
    expect(parseDeepLink(`?view=ecosystem&${url}&capture=1`)).toEqual(FULL);  // other parameters of the page do not disturb it
  });
  it('round-trips a controlled run and every Address form', () => {
    const route: DeepLink = { seed: 2, route: { controller: 'adaptive_shed', scenario: 'coupling weakened (gain 0.5)' }, address: { mode: 'partial', tick: 100, target: 'A1', fraction: 0.5 } };
    expect(parseDeepLink(formatDeepLink(route))).toEqual(route);
    expect(parseDeepLink('address=delayed@80:A2:11,6')).toEqual({ address: { mode: 'delayed', tick: 80, target: 'A2', x: 11, y: 6 } });
    expect(parseDeepLink('address=loss@100').address).toEqual({ mode: 'loss', tick: 100, target: 'A2' });
    expect(parseDeepLink('reconf=fixed|history lost').route).toEqual({ controller: 'fixed', scenario: 'history lost' });  // the earlier alias
  });
  it('ignores what is not a valid value rather than guessing', () => {
    expect(parseDeepLink('seed=abc&tick=&sss=9/1/1&address=nonsense&route=justaword')).toEqual({});
  });
  it('parses and formats the observation both ways', () => {
    const o = parseObs('interval:4,stride:2,region:0.0.6.13,threshold:0.2');
    expect(o).toEqual({ sampling_interval: 4, spatial_stride: 2, region: [0, 0, 6, 13], threshold: 0.2 });
    expect(parseObs(formatObs(o))).toEqual(o);
  });
});

describe('the plan a link gives', () => {
  it('is the same for the same link, and carries everything the link names', () => {
    const p = deepLinkPlan(parseDeepLink(formatDeepLink(FULL)));
    expect(p).toEqual(deepLinkPlan(FULL));
    expect(p.seed).toBe(7); expect(p.tick).toBe(165); expect(p.run).toEqual({ kind: 'mfs', mfs: 'MFS-F14-2' }); expect(p.tab).toBe('research');
    expect(p.obs).toEqual({ ...FULL_OBSERVATION, ...FULL.obs }); expect(p.cam).toBe('body'); expect(p.quality).toBe('balanced');
    expect(p.interventions).toEqual([{ tick: 0, op: 'ALTER_SSS', scale: 1.2, size: 1, speed: 0.9 }, { tick: 100, op: 'ADDRESS', target: 'A2', mode: 'reassign', x: 11, y: 6 }]);
    expect(p.layers).toEqual(['route.fallback', 'mfs.current', 'mfs.rejected']); expect(p.routelayers).toEqual(['active', 'failed']);
  });
  it('defaults: no link is a plain run of seed 1 from tick 0 with full observation', () => {
    const p = deepLinkPlan(parseDeepLink(''));
    expect(p).toMatchObject({ seed: 1, tick: 0, interventions: [], run: { kind: 'plain' }, tab: null, obs: FULL_OBSERVATION });
  });
  it('a route link becomes a controlled run and an MFS link wins over it', () => {
    expect(deepLinkPlan(parseDeepLink('route=fixed:history lost')).run).toEqual({ kind: 'route', controller: 'fixed', scenario: 'history lost' });
    expect(deepLinkPlan(parseDeepLink('route=fixed:history lost&mfs=MFS-F1-1')).run.kind).toBe('mfs');
  });
});
