// Evaluate a given observation configuration the way ARDS evaluates a final configuration (held-out cases, ARDS's own evaluateHeldOut2), on a replicate
// reserved for software tests. Used for arms that are not ARDS arms (the HPO arm of the shared environment), so that every arm is scored by the same
// ARDS code on the same service. Test mode only (replicates 3980-3989).
import { join } from "node:path";
import { envSpec, makeService } from "./common";

const root = process.env.XZR_ARDS_ROOT;
if (!root) throw new Error("XZR_ARDS_ROOT is not set");
const arg = process.argv.slice(2).filter((a) => a !== "--" && !a.endsWith(".ts"));

async function main(): Promise<void> {
  const job = JSON.parse(arg[0] ?? "{}") as { env: string; replicate: number; config: any }; // eslint-disable-line @typescript-eslint/no-explicit-any
  if (!(job.replicate >= 3980 && job.replicate <= 3989)) throw new Error(`software-test replicates only (3980-3989), got ${job.replicate}`);
  const loop2 = await import(join(root!, "src/ards/loop2/index.ts"));
  const planner = await import(join(root!, "src/ards/loop/planner.ts"));
  const env = await envSpec(root!, job.env);
  const service = await makeService(root!, job.env, "zrs-eval");
  const def = await loop2.evaluateHeldOut2(env, service, planner.renameConfig(env.startConfig, "control"), job.replicate);
  const held = await loop2.evaluateHeldOut2(env, service, job.config, job.replicate);
  service.close?.();
  process.stdout.write(JSON.stringify({ held, default: def }) + "\n");
}
main().catch((e) => { console.error(e instanceof Error ? e.stack : e); process.exit(1); });
