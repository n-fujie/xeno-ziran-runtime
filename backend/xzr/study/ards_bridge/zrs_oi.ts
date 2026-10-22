// The shared ARDS-HPO environment as ARDS sees it ("env3"): an ObserveService backed by the Python worker xzr.study.shared.oi_worker (the runtime
// world observed through the HPO instruments), and the EnvSpec that describes it. A NEW environment: it changes no ARDS environment, lives in the
// bridge directory of the simulator repository, and writes nothing into the ARDS repository. Ground truth is returned with every observation (as the
// XB-TRO service does) for evaluation and verification only; the arms never read it.
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createInterface } from "node:readline";
import { join } from "node:path";

export const ENV3_ID = "zrs.oi-env3";

export class OiObserveService {
  readonly kind = "real" as const; // a genuine simulation of the runtime world; not the real world
  readonly id = ENV3_ID;
  calls = 0;
  wallSeconds = 0;
  private proc: ChildProcessWithoutNullStreams | null = null;
  private waiting: ((line: string) => void)[] = [];
  private chain: Promise<unknown> = Promise.resolve();
  private cat: unknown = null;

  constructor(private readonly o: { python: string; backendDir: string }) {}

  private start(): ChildProcessWithoutNullStreams {
    if (this.proc) return this.proc;
    const p = spawn(this.o.python, ["-m", "xzr.study.shared.oi_worker"], { cwd: this.o.backendDir, env: { ...process.env, PYTHONPATH: this.o.backendDir }, stdio: ["pipe", "pipe", "pipe"] });
    createInterface({ input: p.stdout }).on("line", (l) => this.waiting.shift()?.(l));
    p.stderr.on("data", () => undefined);
    this.proc = p;
    return p;
  }
  private rpc(msg: unknown): Promise<any> { // eslint-disable-line @typescript-eslint/no-explicit-any
    const run = async () => {
      const p = this.start();
      const t0 = Date.now();
      const line = await new Promise<string>((res, rej) => { this.waiting.push(res); p.once("exit", () => rej(new Error("oi worker exited"))); p.stdin.write(JSON.stringify(msg) + "\n"); });
      this.wallSeconds += (Date.now() - t0) / 1000;
      const r = JSON.parse(line);
      if (!r.ok) throw new Error(r.error);
      return r;
    };
    const next = this.chain.then(run, run);
    this.chain = next.catch(() => undefined);
    return next;
  }
  close(): void { this.proc?.stdin.end(); this.proc = null; }

  async catalog() { if (!this.cat) this.cat = (await this.rpc({ cmd: "catalog" })).catalog; return this.cat; }
  async capability(_preset: string, configs: readonly unknown[]) { return (await this.rpc({ cmd: "capability", configs })).capability; }
  async observe(req: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
    this.calls++;
    const r = await this.rpc({ cmd: "observe", req, truth: true });
    return { request: req, bodyRuns: r.bodyRuns, configs: r.configs, truth: r.truth, wallSeconds: null, maxRssBytes: null };
  }
}

export function env3Spec() {
  const startConfig = { name: "control", kinds: ["activity", "tension", "memory"], overrides: {}, window: null };
  const c = (id: string, preset: string, alteration: string, seen: boolean) => ({ id, preset, alteration, seen });
  return {
    id: "env3", label: "runtime world observed through HPO instruments (observation-identifiability)", startConfig, loopPreset: "intermittent",
    loopAlterations: ["input-shift", "coupling-shift", "retention-shift"] as [string, string, string], nPerCase: 12,
    frozenNames: {
      kinds: { posture: "activity", emg: "tension", contact: "memory", imu: "structure", respiration: "recursion" },
      alterations: { mixed: "input-shift", "delay-only": "coupling-shift", "tone-only": "retention-shift", "fatigue-only": "threshold-shift" },
      presets: { "human-like-planar": "intermittent", "machine-like-planar": "sparse" },
    },
    cases: [
      c("inter/input-shift", "intermittent", "input-shift", true), c("inter/coupling-shift", "intermittent", "coupling-shift", true), c("inter/retention-shift", "intermittent", "retention-shift", true),
      c("inter/threshold-shift", "intermittent", "threshold-shift", false),
      c("sparse/input-shift", "sparse", "input-shift", false), c("sparse/coupling-shift", "sparse", "coupling-shift", false), c("sparse/retention-shift", "sparse", "retention-shift", false), c("sparse/threshold-shift", "sparse", "threshold-shift", false),
    ],
  };
}
export const join3 = join;
