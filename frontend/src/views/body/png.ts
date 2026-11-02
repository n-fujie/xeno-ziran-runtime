// PNG helpers for figure export: put the figure's metadata into a tEXt chunk of a PNG that the browser made from the SVG, and read it back. The metadata is ASCII JSON (the server provides it).
// The pixels are not examined by anything here.
const SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
let TABLE: Uint32Array | null = null;
function crc32(buf: Uint8Array): number {
  if (!TABLE) { TABLE = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; TABLE[n] = c >>> 0; } }
  let c = 0xffffffff;
  for (const b of buf) c = TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
const u32 = (n: number) => new Uint8Array([(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255]);
const readU32 = (b: Uint8Array, i: number) => ((b[i] << 24) | (b[i + 1] << 16) | (b[i + 2] << 8) | b[i + 3]) >>> 0;

export const isPng = (b: Uint8Array) => SIG.every((v, i) => b[i] === v);

/** Insert a tEXt chunk before IEND. ``value`` must be ASCII (non-ASCII text is refused rather than silently changed). */
export function pngAddText(png: Uint8Array, key: string, value: string): Uint8Array {
  if (!isPng(png)) throw new Error('not a PNG');
  if (/[^\x20-\x7e]/.test(value) || /[^\x20-\x7e]/.test(key)) throw new Error('the text chunk carries ASCII only: escape the metadata (JSON with \\u escapes)');
  const data = new TextEncoder().encode(`${key}\0${value}`), type = new TextEncoder().encode('tEXt');
  const body = new Uint8Array(type.length + data.length); body.set(type); body.set(data, type.length);
  const chunk = new Uint8Array(12 + data.length); chunk.set(u32(data.length)); chunk.set(body, 4); chunk.set(u32(crc32(body)), 8 + data.length);
  let i = 8, iend = -1;
  while (i < png.length) { const n = readU32(png, i); if (String.fromCharCode(...png.slice(i + 4, i + 8)) === 'IEND') { iend = i; break; } i += 12 + n; }
  if (iend < 0) throw new Error('no IEND chunk');
  const out = new Uint8Array(png.length + chunk.length); out.set(png.slice(0, iend)); out.set(chunk, iend); out.set(png.slice(iend), iend + chunk.length);
  return out;
}

export function pngTextChunks(png: Uint8Array): Record<string, string> {
  if (!isPng(png)) throw new Error('not a PNG');
  const out: Record<string, string> = {}; let i = 8;
  while (i < png.length) {
    const n = readU32(png, i), type = String.fromCharCode(...png.slice(i + 4, i + 8)), body = png.slice(i + 4, i + 8 + n);
    if (readU32(png, i + 8 + n) !== crc32(body)) throw new Error('a chunk CRC does not match');
    if (type === 'tEXt') { const d = png.slice(i + 8, i + 8 + n), z = d.indexOf(0); out[new TextDecoder().decode(d.slice(0, z))] = new TextDecoder().decode(d.slice(z + 1)); }
    i += 12 + n;
  }
  return out;
}

/** Rasterise an SVG string to a PNG in the browser (twice the size) and add the metadata chunk. Browser only. */
export async function svgToPng(svg: string, metadataAscii: string, scale = 2): Promise<Uint8Array> {
  const img = new Image(), url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }));
  await new Promise<void>((ok, bad) => { img.onload = () => ok(); img.onerror = () => bad(new Error('the SVG could not be rasterised')); img.src = url; });
  const c = document.createElement('canvas'); c.width = img.width * scale; c.height = img.height * scale;
  const g = c.getContext('2d'); if (!g) throw new Error('no canvas'); g.drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url);
  const blob: Blob = await new Promise((ok, bad) => c.toBlob((b) => (b ? ok(b) : bad(new Error('no PNG'))), 'image/png'));
  return pngAddText(new Uint8Array(await blob.arrayBuffer()), 'teoo-metadata', metadataAscii);
}
