import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';

// Build of the read-only TEOO preview (npm run build:teoo-preview): one page, fixtures only, no network beyond the page's own origin.
const CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
  + "object-src 'none'; base-uri 'none'; form-action 'none'; frame-src 'none'";

function shell(): Plugin {
  return {
    name: 'teoo-preview-shell',
    enforce: 'pre',
    transform(code, id) { return id.endsWith('styles.css') ? code.replace(/@import url\('https:\/\/fonts\.googleapis\.com[^)]*\);\n?/, '') : null; },
    transformIndexHtml(html) { return html.replace('<meta charset="UTF-8" />', `<meta charset="UTF-8" />\n    <meta http-equiv="Content-Security-Policy" content="${CSP}" />`); },
  };
}

export default defineConfig({
  plugins: [react(), shell()],
  define: { 'import.meta.env.VITE_TEOO_PREVIEW': JSON.stringify('1') },
  build: { outDir: '../site-teoo-preview', emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 2500, rollupOptions: { input: 'teoo-preview.html' } },
});
