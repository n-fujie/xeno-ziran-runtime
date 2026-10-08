import { describe, expect, it } from 'vitest';
import { pageTitle, searchForView, unknownRoute, viewFromSearch } from './routing';
import type { View } from './store/sim';

const ALLOWED: View[] = ['overview', 'res_matrix', 'reduction'];

describe('view routing', () => {
  it('reads the view from the query and falls back for unknown or missing views', () => {
    expect(viewFromSearch('?view=res_matrix', ALLOWED, 'overview')).toBe('res_matrix');
    expect(viewFromSearch('?view=nonexistent', ALLOWED, 'overview')).toBe('overview');
    expect(viewFromSearch('', ALLOWED, 'overview')).toBe('overview');
  });

  it('reads view ids case-insensitively, as the host routes them', () => {
    expect(viewFromSearch('?view=RES_Matrix', ALLOWED, 'overview')).toBe('res_matrix');
    expect(unknownRoute('/', '?view=OVERVIEW', ALLOWED)).toBeNull();
  });

  it('writes the view into the query, keeps other parameters, and omits the default view', () => {
    expect(searchForView('?scenario=demo-3k', 'reduction', 'overview')).toBe('?scenario=demo-3k&view=reduction');
    expect(searchForView('?view=reduction&lang=ja', 'overview', 'overview')).toBe('?lang=ja');
    expect(searchForView('', 'overview', 'overview')).toBe('');
  });

  it('round-trips every allowed view', () => {
    for (const v of ALLOWED) expect(viewFromSearch(searchForView('', v, 'overview'), ALLOWED, 'overview')).toBe(v);
  });

  it('reports unknown paths and unknown view values, and nothing for addressable views', () => {
    expect(unknownRoute('/', '', ALLOWED)).toBeNull();
    expect(unknownRoute('/', '?view=reduction&lang=ja', ALLOWED)).toBeNull();
    expect(unknownRoute('/index.html', '?view=overview', ALLOWED)).toBeNull();
    expect(unknownRoute('/', '?view=nonexistent', ALLOWED)).toBe('?view=nonexistent');
    expect(unknownRoute('/', '?view=', ALLOWED)).toBe('?view=');
    expect(unknownRoute('/does/not/exist', '', ALLOWED)).toBe('/does/not/exist');
  });

  it('titles a view with the application name', () => {
    expect(pageTitle('Resolution Matrix')).toBe('Resolution Matrix — XENO ZIRAN SIMULATOR');
  });
});
