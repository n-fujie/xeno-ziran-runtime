// Overview tab of the static site: the Ziran / Xeno Simulator project page (built by that repository's
// site/build.ts and exported next to this app under /overview/) rendered in place. It is mounted in a shadow root so
// that its stylesheet and this app's stylesheet cannot affect each other.
import { useEffect, useRef, useState } from 'react';

const BASE = '/overview/';

function adapt(html: string): { css: string; body: string } {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const css = Array.from(doc.querySelectorAll('style')).map((s) => s.textContent ?? '').join('\n')
    .replace(/:root/g, ':host')
    .replace(/(^|[}\s,])body(?=[\s{,])/g, '$1.ov-body')
    // this site is dark: use the page's own dark palette regardless of the viewer's colour scheme
    .replace(/@media\s*\(prefers-color-scheme:\s*dark\)\s*\{([^{}]*\{[^{}]*\})\}/g, '$1');
  doc.querySelectorAll('[src]').forEach((el) => {
    const v = el.getAttribute('src') ?? '';
    if (!/^(https?:|data:|\/)/.test(v)) el.setAttribute('src', BASE + v);
  });
  doc.querySelectorAll('a[href]').forEach((el) => {
    const v = el.getAttribute('href') ?? '';
    if (!/^(https?:|mailto:|#|\/)/.test(v)) el.setAttribute('href', BASE + v);
    if (/^https?:/.test(v)) el.setAttribute('target', '_blank');
  });
  return { css, body: doc.body.innerHTML };
}

export default function OverviewView() {
  const host = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    fetch(BASE + 'index.html')
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((html) => {
        if (!alive || !host.current) return;
        const root = host.current.shadowRoot ?? host.current.attachShadow({ mode: 'open' });
        const { css, body } = adapt(html);
        root.innerHTML = `<style>:host{display:block;color-scheme:dark}${css}.ov-body{background:transparent}</style>` +
          `<div class="ov-body">${body}</div>`;
      })
      .catch((e) => setError(String(e)));
    return () => { alive = false; };
  }, []);
  return (
    <div className="panel-view overview">
      {error && <div className="dim">The project overview is not available in this build ({error}).</div>}
      <div ref={host} />
    </div>
  );
}
