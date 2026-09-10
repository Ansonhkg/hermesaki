import type { Workflow, Capture } from "./contracts";
export function layout(w: Workflow) {
  const ids = new Set(w.nodes.map((n) => n.id));
  if (ids.size !== w.nodes.length) throw Error("Duplicate node");
  const rank = new Map(w.nodes.map((n) => [n.id, 0])),
    degree = new Map(w.nodes.map((n) => [n.id, 0]));
  w.edges.forEach(([a, b]) => {
    if (!ids.has(a) || !ids.has(b)) throw Error("Unknown edge");
    degree.set(b, degree.get(b)! + 1);
  });
  const queue = w.nodes.filter((n) => degree.get(n.id) === 0).map((n) => n.id);
  let seen = 0;
  while (queue.length) {
    const id = queue.shift()!;
    seen++;
    for (const [a, b] of w.edges)
      if (a === id) {
        rank.set(b, Math.max(rank.get(b)!, rank.get(a)! + 1));
        degree.set(b, degree.get(b)! - 1);
        if (!degree.get(b)) queue.push(b);
      }
  }
  if (seen !== w.nodes.length) throw Error("Workflow must be acyclic");
  const lanes = new Map<number, number>();
  return w.nodes.map((n) => {
    const r = rank.get(n.id)!,
      lane = lanes.get(r) || 0;
    lanes.set(r, lane + 1);
    return { ...n, x: 24 + r * 190, y: 35 + lane * 100 };
  });
}
export const clock = (ms: number) =>
  `${Math.floor(ms / 60000)
    .toString()
    .padStart(
      2,
      "0",
    )}:${Math.floor(ms / 1000) % 60 < 10 ? "0" : ""}${Math.floor(ms / 1000) % 60}`;
export function workflowPlayback(captures: Capture[], workflow: Workflow) {
  const order = workflow.chapters?.flatMap((c) => c.steps) ?? workflow.route;
  const ordered = captures
    .map((capture, index) => ({ capture, index }))
    .sort((a, b) => {
      const rank = (id: string) => {
        const i = order.indexOf(id);
        return i < 0 ? order.length : i;
      };
      return (
        rank(a.capture.stepId) - rank(b.capture.stepId) || a.index - b.index
      );
    });
  let playAt = 0;
  return ordered.map(({ capture }, i) => {
    if (i)
      playAt += Math.max(
        3000,
        Math.min(5000, capture.at - ordered[i - 1].capture.at),
      );
    return { ...capture, playAt };
  });
}

export function recordingProgress(
  run: import("./contracts").Recording,
  workflow: Workflow,
) {
  const definition = run.definition ?? workflow,
    captured = new Set(run.captures.map((c) => c.stepId)),
    missing = definition.route.filter((id) => !captured.has(id));
  const complete = missing.length === 0 && run.outcome === "passed";
  return {
    complete,
    count: definition.route.length - missing.length,
    total: definition.route.length,
    next: definition.nodes.find((n) => n.id === missing[0])?.label,
    label: complete
      ? "Complete"
      : run.outcome === "failed"
        ? "Failed"
        : missing.length
          ? "Incomplete"
          : "Captured; unverified",
  };
}
export function latestRecording(
  runs: import("./contracts").Recording[],
  workflow: Workflow,
) {
  const matching = runs
    .filter((r) => r.workflow === workflow.id)
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  return (
    matching.find((r) => recordingProgress(r, workflow).complete) ??
    matching.find((r) => {
      const p = recordingProgress(r, workflow);
      return (
        p.count === p.total && r.outcome !== "failed" && r.outcome !== "running"
      );
    }) ??
    matching[0]
  );
}
