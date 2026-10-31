// Read-only preview of BODY / TOTAL OBSERVATION (Views A-H): the same components as the local app, fed from fixed SYNTHETIC fixtures (VITE_TEOO_PREVIEW=1). No simulator, no API, no upload, no stored data.
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import Workspace from './views/body/Workspace';

function Preview() {
  return (
    <div style={{ maxWidth: 1280, margin: '0 auto', padding: '12px 16px' }}>
      <div role="note" data-testid="teoo-preview-notice" className="small" style={{ border: '1px solid #c9a227', padding: '8px 12px', marginBottom: 10, color: '#ffe9b0' }}>
        <b>PREVIEW — read-only.</b> Every record on this page is SYNTHETIC (an artificial generator) or a drawing; there is no measurement, no human data, no upload and no server-side state. The data are fixed files written by the backend; the
        local research API, its authentication and its limits are not part of this page and are not exposed. Nothing here supports any claim about a real body.
      </div>
      <Workspace />
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<StrictMode><Preview /></StrictMode>);
