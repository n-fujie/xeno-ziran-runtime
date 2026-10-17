import { useEffect, useState } from 'react';
import { webStatus, type WebStatus } from '../api/webRuntime';
import { useSim } from '../store/sim';

/** Progress of the in-tab runtime while it downloads and starts (browser build only). */
export default function WebBoot() {
  const [s, setS] = useState<WebStatus>(webStatus());
  useEffect(() => {
    const on = (e: Event) => setS((e as CustomEvent<WebStatus>).detail);
    window.addEventListener('xzr-web-status', on);
    setS(webStatus());
    return () => window.removeEventListener('xzr-web-status', on);
  }, []);
  const text: Record<WebStatus['phase'], string> = {
    idle: 'starting the simulator in your browser…', manifest: 'starting the simulator in your browser…',
    runtime: 'downloading the Python runtime (first start only, cached afterwards)…', packages: 'loading numpy and pydantic…',
    engine: 'loading the simulator engine…', ready: 'building scenario…', failed: 'The in-browser runtime could not start.',
  };
  return (
    <>
      {text[s.phase]}
      {s.phase === 'failed' && s.message ? <> <span className="mono">{s.message}</span></> : null}
      {s.phase === 'failed' && <> <button onClick={() => void useSim.getState().resumeOrOpen(null)}>Retry</button></>}
    </>
  );
}
