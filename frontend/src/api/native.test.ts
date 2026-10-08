import { describe, expect, it } from 'vitest';
import { base64ToBytes, toResponse } from './native';

describe('native transport', () => {
  it('turns bridge replies into fetch Responses of the same shape as the HTTP service', async () => {
    const json = toResponse({ status: 404, kind: 'json', body: { detail: 'no such session' } });
    expect(json.status).toBe(404);
    expect(json.headers.get('content-type')).toContain('json');
    expect(await json.json()).toEqual({ detail: 'no such session' });

    const text = toResponse({ status: 200, kind: 'text', body: 'id,x\n0,1\n' });
    expect(await text.text()).toBe('id,x\n0,1\n');

    const bin = toResponse({ status: 200, kind: 'binary', body: btoa(String.fromCharCode(1, 2, 255)) });
    expect(Array.from(new Uint8Array(await bin.arrayBuffer()))).toEqual([1, 2, 255]);
  });

  it('decodes base64 losslessly', () => {
    const bytes = Uint8Array.from({ length: 256 }, (_, i) => i);
    expect(Array.from(base64ToBytes(btoa(String.fromCharCode(...bytes))))).toEqual(Array.from(bytes));
  });
});
