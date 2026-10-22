// Shared by the bridge jobs: building the ObserveService and the EnvSpec of an environment, and the software-test parameters of the fixed-strategy arms.
import { join } from "node:path";
import { OiObserveService, env3Spec } from "./zrs_oi";

export async function makeService(root: string, envId: string, tag: string): Promise<any> { // eslint-disable-line @typescript-eslint/no-explicit-any
  const loop2 = await import(join(root, "src/ards/loop2/index.ts"));
  if (envId === "env2") return new loop2.OscillatorObserveService();
  if (envId === "env3") {
    return new OiObserveService({ python: process.env.XZR_PYTHON ?? "python3", backendDir: join(__dirname, "..", "..", "..") });
  }
  const ards = await import(join(root, "src/ards/index.ts"));
  const { ExperimentalBackendRegistry } = await import(join(root, "src/ziran/experimental/registry.ts"));
  const bim = join(root, "..");
  const backends = new ExperimentalBackendRegistry();
  backends.register(new ards.XbtroObserveBackend({ python: join(bim, "xeno-ziran-runtime", ".venv", "bin", "python"), xzrRoot: join(bim, "xeno-ziran-runtime-xb-tro"),
    workerScript: join(root, "python", "ards_worker", "worker.py"), clock: ards.SystemClock, env: {} }));
  return new ards.RealObserveService(backends, tag);
}

export async function envSpec(root: string, envId: string): Promise<any> { // eslint-disable-line @typescript-eslint/no-explicit-any
  const loop2 = await import(join(root, "src/ards/loop2/index.ts"));
  return envId === "env3" ? env3Spec() : loop2.ENVS[envId];
}

/** Software-test parameters of the fixed-strategy arms (never exploration-derived values). The devices must exist in the environment. */
export const fixedParams = (envId: string) => ({ noiseFactor: 0.5, addDevices: envId === "env3" ? ["structure", "recursion"] : ["imu", "respiration"] });
