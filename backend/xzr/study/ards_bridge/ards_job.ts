// XENO ZIRAN SIMULATOR study bridge to ARDS (pa-simulation-environment). One job = one arm on one replicate in one ARDS environment, in ARDS "test"
// mode only: the ARDS study gate (studyGuard.assertRunAllowed) accepts only replicates 3980-3989 there, so no exploration or study data can be produced
// through this bridge and nothing is written into the ARDS repository. The output is one JSON object on stdout.
//
//   vite-node ards_job.ts -- describe                                   -> the ARDS arm registry (roles, information, permissions)
//   vite-node ards_job.ts -- run '{"env":"env2","arm":"V2-PA","replicate":3981}'
import { join } from "node:path";

const root = process.env.XZR_ARDS_ROOT;
if (!root) throw new Error("XZR_ARDS_ROOT is not set");
const arg = process.argv.slice(2).filter((a) => a !== "--" && !a.endsWith(".ts"));

async function main(): Promise<void> {
  const loop2 = await import(join(root!, "src/ards/loop2/index.ts"));
  if (arg[0] === "describe") {
    process.stdout.write(JSON.stringify({ arms: loop2.ARMS, envs: Object.keys(loop2.ENVS) }) + "\n");
    return;
  }
  const job = JSON.parse(arg[1] ?? "{}") as { env: "env1" | "env2"; arm: string; replicate: number };
  const env = loop2.ENVS[job.env];
  if (!env) throw new Error(`unknown ARDS environment ${job.env}`);
  const spec = loop2.ARMS.find((a: { id: string }) => a.id === job.arm);
  if (!spec) throw new Error(`unknown ARDS arm ${job.arm}`);
  if (job.arm.endsWith("shuffled")) throw new Error("shuffled arms need another replicate's run and are not available through the bridge");
  let service;
  if (job.env === "env2") service = new loop2.OscillatorObserveService();
  else {
    const ards = await import(join(root!, "src/ards/index.ts"));
    const { ExperimentalBackendRegistry } = await import(join(root!, "src/ziran/experimental/registry.ts"));
    const bim = join(root!, "..");
    const backends = new ExperimentalBackendRegistry();
    backends.register(new ards.XbtroObserveBackend({ python: join(bim, "xeno-ziran-runtime", ".venv", "bin", "python"), xzrRoot: join(bim, "xeno-ziran-runtime-xb-tro"),
      workerScript: join(root!, "python", "ards_worker", "worker.py"), clock: ards.SystemClock, env: {} }));
    service = new ards.RealObserveService(backends, "zrs-bridge");
  }
  const t0 = Date.now();
  // software-test parameters of the fixed-strategy arms (not exploration-derived values)
  const rec = await loop2.runReplicate({ env, service, replicate: job.replicate, foreignReplicate: job.replicate, mode: "test", arms: [job.arm], fixed: { noiseFactor: 0.5, addDevices: ["imu", "respiration"] } });
  const a = rec.arms[job.arm];
  process.stdout.write(JSON.stringify({ spec, metrics: a.metrics, verification: a.verification, verificationFailed: a.verificationFailed, runSummary: a.runSummary,
    default: { unseenCoverage: rec.default.ratesUnseen.coverage, seenCoverage: rec.default.ratesSeen.coverage }, wallSeconds: (Date.now() - t0) / 1000 }) + "\n");
}
main().catch((e) => { console.error(e instanceof Error ? e.stack : e); process.exit(1); });
