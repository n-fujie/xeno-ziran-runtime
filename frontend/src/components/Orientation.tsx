// Entry orientation of the static site: what the application is, how its operational regions relate, what this
// deployment shows (generated research results, read-only), and what only the interactive runtime does (it is not
// part of this deployment).
import type { View } from '../store/sim';

export default function Orientation({ views, onOpen }: {
  views: { id: View; label: string }[];
  onOpen: (v: View) => void;
}) {
  return (
    <section className="orientation" aria-labelledby="orientation-h">
      <h2 id="orientation-h">XENO ZIRAN SIMULATOR</h2>
      <p>
        An environment for exploring how differences propagate across configurations under changes in scale,
        topology, memory, coupling, observation, history, boundary and intervention. It does not fix the variables,
        state space, observer or ontology in advance.
      </p>
      <div className="small dim layers">
        <p>
          Operational-Shape Dynamics (theory) › Xenoscience (scientific regime) › Ziran System (architecture family) ›
          <b> XENO ZIRAN SIMULATOR</b> (this application), whose operations fall into distinct regions:
        </p>
        <ul className="regions">
          <li><b>Experimental runtime</b> — configuration, intervention, execution, branch comparison, replay</li>
          <li><b>Research results</b> — the experiment suites run on that runtime and their machine-readable results</li>
          <li><b>Philosophical Runtime</b> — philosophical analysis: claims and commitments entered as structured
            interventions and traced through the same runtime</li>
        </ul>
      </div>
      <div className="orient-cols">
        <div>
          <h3>On this site — generated research results (read-only)</h3>
          <p className="small">
            Each view reads the machine-readable result files produced by experiment runs and shows them as generated:
            conditions without a detected difference, noise floors and caveats included. Nothing is simulated in the
            browser. The currently published result views are experimental and analytical outputs and should not be
            interpreted as real-world forecasts or predictive claims. Each view offers its source JSON for download.
          </p>
          <p className="small">
            Reading a null result: "not detected" means no difference above the stated noise floor at that resolution
            and time window — not that none exists. It is kept apart from a condition or resolution that was not
            measured, from a mismatch of measurement apparatus, scale or time window, and from a difference that is
            present but inaccessible to the observation used. Bit-identical runs mean that no difference was detected
            within the represented and measured state under the stated comparison procedure; equivalence within a
            stated margin is reported as such. Neither is a claim of genuine absence, which would need independent
            justification beyond these measurements.
          </p>
          <div className="orient-views">
            {views.map((v) => <button key={v.id} onClick={() => onOpen(v.id)}>{v.label}</button>)}
          </div>
        </div>
        <div>
          <h3>Interactive runtime — in your browser at /app/, or on a local server</h3>
          <p className="small">
            The simulator runs in your browser tab at <a href="/app/">/app/</a> (smaller workloads, nothing is sent to a
            server) or against a local backend for full-size runs: configure a scenario → intervene (practice console,
            intervention grammar) → run / step / rewind → compare baseline and intervention branches → inspect
            network, shape-space, address-space, map and globe projections and the timeline → save / load → export
            CSV / JSON. The research-result views on this page are read-only: no simulation runs here.
          </p>
        </div>
      </div>
    </section>
  );
}
