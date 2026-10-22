// Reference path for the bridge check: the same arm on the same replicate through ARDS's own building blocks as its scripts use them
// (runArm -> verifyArmRun -> evaluateHeldOut2 -> armMetrics, as in scripts/ardsV2RealSmoke.ts), NOT through runReplicate. If the bridge (which
// uses runReplicate) and this path give identical metrics, the bridge adds nothing and changes nothing. Test mode only (replicates 3980-3989).
import { join } from "node:path";
import { envSpec, fixedParams, makeService } from "./common";

const root = process.env.XZR_ARDS_ROOT;
if (!root) throw new Error("XZR_ARDS_ROOT is not set");
const arg = process.argv.slice(2).filter((a) => a !== "--" && !a.endsWith(".ts"));

async function main(): Promise<void> {
  const loop2 = await import(join(root!, "src/ards/loop2/index.ts"));
  const planner = await import(join(root!, "src/ards/loop/planner.ts"));
  const job = JSON.parse(arg[0] ?? "{}") as { env: "env1" | "env2" | "env3"; arm: string; replicate: number };
  const env = await envSpec(root!, job.env);
  const service = await makeService(root!, job.env, "zrs-direct");
  const catalog = await service.catalog();
  const run = await loop2.runArm(job.arm, { env, service, replicate: job.replicate, mode: "test", fixed: fixedParams(job.env) });
  const checks = loop2.verifyArmRun(run, env, catalog);
  const def = await loop2.evaluateHeldOut2(env, service, planner.renameConfig(env.startConfig, "control"), job.replicate);
  const held = await loop2.evaluateHeldOut2(env, service, run.finalConfig, job.replicate);
  const metrics = loop2.armMetrics(run, held, def);
  service.close?.();
  process.stdout.write(JSON.stringify({ metrics, verificationFailed: checks.filter((c: { pass: boolean }) => !c.pass), verificationChecks: checks.length }) + "\n");
}
main().catch((e) => { console.error(e instanceof Error ? e.stack : e); process.exit(1); });
