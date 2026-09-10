import type { Capture, Guide, Recording, Step, Workflow } from "./contracts";
export type Context = Record<string, string>;
export type Runtime = {
  context: Context;
  wait: (check: () => Promise<boolean>, timeout?: number) => Promise<void>;
  rpc: (
    surface: string,
    type: string,
    key?: string,
    context?: Context,
  ) => Promise<any>;
};
export type PlannedStep = {
  step: Step;
  key?: string;
  guide: Guide;
  path?: string;
  after?: (runtime: Runtime) => Promise<void>;
  manual?: (runtime: Runtime) => Promise<void>;
  afterCapture?: "input" | "server" | "navigation";
  ready?: (reply: any) => boolean;
};
export type ExecutionPlan = {
  prepare: () => Promise<Context>;
  steps: (
    context: Context,
  ) => AsyncIterable<PlannedStep> | Iterable<PlannedStep>;
  cleanup?: (context: Context) => Promise<void>;
};
export type RunOptions = {
  workflow: Workflow;
  plan: ExecutionPlan;
  signal: AbortSignal;
  select: (id: string, surface: string, path?: string) => void;
  prepare: (context: Context) => void;
  rpc: Runtime["rpc"];
  save: (recording: Recording) => Promise<void>;
  stopped?: () => boolean;
  timing?: { settle: number; after: number; poll: number };
};
export async function runWalkthrough(o: RunOptions) {
  const start = Date.now(),
    timing = o.timing ?? { settle: 700, after: 600, poll: 500 };
  const check = () => {
    if (o.signal.aborted || o.stopped?.()) throw Error("Walkthrough stopped.");
  };
  const pause = (ms: number) =>
    new Promise<void>((resolve, reject) => {
      check();
      const abort = () => {
        clearTimeout(timer);
        reject(Error("Walkthrough stopped."));
      };
      const timer = setTimeout(() => {
        o.signal.removeEventListener("abort", abort);
        try {
          check();
          resolve();
        } catch (e) {
          reject(e);
        }
      }, ms);
      o.signal.addEventListener("abort", abort, { once: true });
    });
  const wait = async (fn: () => Promise<boolean>, timeout = 15000) => {
    const end = Date.now() + timeout;
    while (Date.now() <= end) {
      check();
      try {
        if (await fn()) return;
      } catch (e) {
        check();
      }
      await pause(timing.poll);
    }
    throw Error("Expected result did not appear.");
  };
  let context: Context = {};
  let run: Recording = {
    id: crypto.randomUUID(),
    workflow: o.workflow.id,
    schemaVersion: 1,
    definition: structuredClone(o.workflow),
    createdAt: new Date().toISOString(),
    outcome: "running",
    captures: [],
  };
  const shot = async (
    p: PlannedStep,
    verified: boolean,
    kind: Capture["check"],
    click = false,
  ) => {
    check();
    const c = await o.rpc(
      p.step.surface,
      "capture",
      kind === "server" || kind === "navigation" ? undefined : p.key,
      context,
    );
    run = {
      ...run,
      captures: [
        ...run.captures,
        {
          ...c,
          stepId: p.step.id,
          surface: p.step.surface,
          at: Date.now() - start,
          verified,
          check: kind,
          guide:
            kind === "server" || kind === "navigation"
              ? { caption: p.step.expected, action: "inspect" }
              : structuredClone(p.guide),
          click,
        },
      ],
    };
    await o.save(run);
  };
  try {
    context = await o.plan.prepare();
    check();
    o.prepare(context);
    for await (const p of o.plan.steps(context)) {
      check();
      o.select(p.step.id, p.step.surface, p.path);
      await wait(async () => {
        const r = await o.rpc(p.step.surface, "guide", p.key, context);
        if (!r.ok) return false;
        if (p.ready) return p.ready(r);
        if (!p.path) return true;
        const u = new URL(p.path, "https://example.invalid");
        return (
          r.url === u.pathname &&
          (!u.searchParams.has("mode") || r.mode === u.searchParams.get("mode"))
        );
      });
      await pause(timing.settle);
      await shot(p, p.guide.action === "inspect", "target");
      if (p.manual) await p.manual({ context, wait, rpc: o.rpc });
      else if (p.guide.action !== "inspect") {
        const result = await o.rpc(p.step.surface, "perform", p.key, context);
        if (!result.ok) throw Error(result.error || "Action failed.");
        if (p.guide.action === "click") {
          run.captures[run.captures.length - 1].click = true;
          await o.save(run);
        }
      }
      if (p.after) await p.after({ context, wait, rpc: o.rpc });
      await pause(timing.after);
      if (p.afterCapture || p.guide.action === "fill")
        await shot(p, true, p.afterCapture ?? "input");
    }
    run = { ...run, outcome: "passed" };
    await o.save(run);
    return run;
  } catch (e) {
    run = {
      ...run,
      outcome: "failed",
      error: e instanceof Error ? e.message : "Run failed",
    };
    try {
      await o.save(run);
    } catch {}
    throw e;
  } finally {
    await o.plan.cleanup?.(context);
  }
}
