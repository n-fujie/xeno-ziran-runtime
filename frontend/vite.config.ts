import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';

const backend = process.env.XZR_BACKEND ?? 'http://127.0.0.1:3011';

// iOS app build (VITE_NATIVE=1, `npm run build:native`): the page is served from the app bundle and must work
// offline and load nothing remote — the web-font import is dropped (system fonts are used), the public-site
// metadata and no-JavaScript text are replaced, and a Content-Security-Policy forbids any network connection.
const NATIVE = process.env.VITE_NATIVE === '1';
// Browser build (VITE_WEBRT=1, `npm run build:web`): the same interactive app with the engine running in the tab
// (Pyodide in a Web Worker). Served at /app/ of the public site; loads nothing from other origins.
const WEBRT = process.env.VITE_WEBRT === '1';
const WEB_CSP = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
  + "font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'none'; frame-src 'none'";
const CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
  + "font-src 'self' data:; connect-src 'self' data: blob:; worker-src 'self' blob:; object-src 'none'; "
  + "base-uri 'none'; form-action 'none'; frame-src 'none'";

function nativeShell(): Plugin {
  const csp = WEBRT ? WEB_CSP : CSP;
  const placeholder = WEBRT
    ? '<div id="root"><main style="padding:40px 16px;font:14px system-ui;color:#d8d8dc">starting the simulator in your browser…<br><br>The first start downloads the runtime from this site (about 11 MB compressed, cached afterwards).<br>It runs entirely in this tab.</main></div>\n  </body>'
    : '<div id="root"><main style="padding:40px 16px;font:14px system-ui;color:#d8d8dc">starting the simulator…</main></div>\n  </body>';
  return {
    name: 'xzr-native-shell',
    enforce: 'pre',
    transform(code, id) {
      if (id.endsWith('styles.css')) return code.replace(/@import url\('https:\/\/fonts\.googleapis\.com[^)]*\);\n?/, '');
      return null;
    },
    transformIndexHtml(html) {
      return html
        .replace(/\s*<link rel="canonical"[^>]*>/, '')
        .replace(/\s*<meta (property="og:|name="twitter:)[^>]*>/g, '')
        .replace('width=device-width, initial-scale=1.0', 'width=device-width, initial-scale=1.0, viewport-fit=cover')
        .replace('<meta charset="UTF-8" />', `<meta charset="UTF-8" />\n    <meta http-equiv="Content-Security-Policy" content="${csp}" />`)
        .replace(/<div id="root">[\s\S]*?<\/div>\n {2}<\/body>/,
          placeholder);
    },
  };
}

export default defineConfig({
  plugins: [react(), ...(NATIVE || WEBRT ? [nativeShell()] : [])],
  base: WEBRT ? '/app/' : NATIVE ? './' : '/',
  worker: { format: 'es' },
  server: {
    port: 5173,
    proxy: {
      '/api': backend,
      '/ws': { target: backend.replace(/^http/, 'ws'), ws: true },
    },
  },
  build: NATIVE
    ? { chunkSizeWarningLimit: 2500, sourcemap: false, outDir: '../ios/build/web', emptyOutDir: true }
    : WEBRT
      ? { chunkSizeWarningLimit: 2500, sourcemap: false, outDir: '../web-app-build', emptyOutDir: true }
      : { chunkSizeWarningLimit: 2500, sourcemap: false },
  test: { environment: 'node' },
});
