import { describe, expect, it } from 'vitest';
import { assemble, makeLoader, plan, RATIO, wanted, type IndexEntry, type Plan } from './results';

describe('section selection', () => {
  it('includes overlapping sections and excludes subtrees', () => {
    expect(wanted(['matrix', 'rows'], { include: ['matrix'] })).toBe(true);
    expect(wanted(['systematic'], { include: ['systematic.variants'] })).toBe(true);  // unsplit parent holds it
    expect(wanted(['answers', '3'], { include: ['matrix'] })).toBe(false);
    expect(wanted(['systematic', 'raw'], { exclude: ['systematic.raw'] })).toBe(false);
    expect(wanted(['systematic', 'variants'], { exclude: ['systematic.raw'] })).toBe(true);
    expect(wanted(['anything'])).toBe(true);
  });

  it('reassembles in the given order', () => {
    const o = assemble([[['a'], 1], [['b', 'x'], 2], [['b', 'y'], 3], [['c'], 4]]);
    expect(JSON.stringify(o)).toBe('{"a":1,"b":{"x":2,"y":3},"c":4}');
  });
});

// original: { a: 1, big: { x: [1, 2], y: 'y' }, c: { d: 1 } }; a and big.y are small, big.x and c are large
const entry: IndexEntry = {
  full: 100, small: ['/data/parts/r/small.json', 5],
  sections: [[['a'], null, 0], [['big', 'x'], '/data/parts/r/x.json', 60], [['big', 'y'], null, 0], [['c'], '/data/parts/r/c.json', 20]],
};
const files: Record<string, unknown> = {
  '/data/parts/r/small.json': [[['a'], 1], [['big', 'y'], 'y']],
  '/data/parts/r/x.json': [1, 2], '/data/parts/r/c.json': { d: 1 },
  '/api/experiments/r': { a: 1, big: { x: [1, 2], y: 'y' }, c: { d: 1 } }, '/api/experiments/w': { whole: true },
};

describe('strategy rule', () => {
  it('uses sections only when they are clearly smaller than the whole file', () => {
    expect(plan('r', entry, { include: ['c'] }, false)).toEqual(
      { strategy: 'sections', files: ['/data/parts/r/c.json'], required: 20, full: 100 });
    expect(plan('r', entry, { include: ['a', 'c'] }, false).files).toEqual(['/data/parts/r/small.json', '/data/parts/r/c.json']);
    const most = plan('r', entry, { exclude: ['big.y'] }, false);  // 5 + 60 + 20 = 85 < 90
    expect(most.strategy).toBe('sections');
    expect(plan('r', entry, undefined, false).strategy).toBe('sections');  // all sections: 85 < 0.9 × 100
  });

  it('switches to the whole file at RATIO of its compressed size, when already loaded, or without sections', () => {
    const heavy: IndexEntry = { ...entry, sections: entry.sections.map(([p, f, c]) => [p, f, f ? c + 5 : 0]) };  // 5 + 65 + 25 = 95
    expect(plan('r', heavy, undefined, false).strategy).toBe('whole');
    expect(95 >= RATIO * heavy.full).toBe(true);
    expect(plan('r', entry, { include: ['c'] }, true)).toMatchObject({ strategy: 'whole', files: ['/api/experiments/r'] });
    expect(plan('w', undefined, { include: ['x'] }, false)).toMatchObject({ strategy: 'whole', files: ['/api/experiments/w'] });
  });
});

describe('loader', () => {
  const setup = () => {
    const calls: string[] = [];
    const reports: string[] = [];
    const plans: [string, Plan][] = [];
    const pending: (() => void)[] = [];
    const load = makeLoader((u) => { calls.push(u); return new Promise((res) => pending.push(() => res(structuredClone(files[u])))); },
      { r: entry }, (m) => reports.push(m), (n, p) => plans.push([n, p]));
    const flush = async () => { while (pending.length) { pending.splice(0).forEach((f) => f()); await Promise.resolve(); await Promise.resolve(); } };
    return { calls, reports, plans, load, flush };
  };

  it('requests every needed file before any arrives (one round), and reassembles in file order', async () => {
    const { load, calls, flush } = setup();
    const p = load<Record<string, unknown>>('r', { include: ['a', 'big', 'c'] });
    await Promise.resolve();
    expect(calls).toEqual(['/data/parts/r/small.json', '/data/parts/r/x.json', '/data/parts/r/c.json']);  // all in flight
    await flush();
    expect(JSON.stringify(await p)).toBe('{"a":1,"big":{"x":[1,2],"y":"y"},"c":{"d":1}}');
  });

  it('caches per page load, and reports a read of a section that was not loaded', async () => {
    const { load, calls, reports, flush } = setup();
    const p1 = load<Record<string, unknown>>('r', { include: ['c'] }); await flush();
    const part = await p1;
    const p2 = load('r', { include: ['c'] }); await flush(); await p2;
    expect(calls).toEqual(['/data/parts/r/c.json']);
    expect(part.big).toBeUndefined();
    expect(reports).toEqual(['result section "big" of r was not loaded for this view']);
  });

  it('fetches the whole file when the rule says so, and files without sections whole', async () => {
    const { load, calls, plans, flush } = setup();
    const p = load('w', { include: ['x'] }); await flush();
    expect(await p).toEqual({ whole: true });
    expect(calls).toEqual(['/api/experiments/w']);
    expect(plans[0][1].strategy).toBe('whole');
  });
});
