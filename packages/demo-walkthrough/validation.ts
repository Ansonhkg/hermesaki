import { layout } from "./model";
import type { Recording, Workflow } from "./contracts";
export type RecordingPolicy = {
  workflows: Workflow[];
  origins: (workflow: string) => string[];
  maxCaptures?: number;
  maxHtml?: number;
  maxBytes?: number;
  maxDuration?: number;
};
export function validateRecording(
  value: unknown,
  p: RecordingPolicy,
): Recording {
  const r = value as Recording,
    w = p.workflows.find((w) => w.id === r?.workflow);
  if (
    !w ||
    typeof r.id !== "string" ||
    !/^[-a-f0-9]{36}$/.test(r.id) ||
    !Array.isArray(r.captures) ||
    (!r.captures.length && r.outcome !== "failed") ||
    r.captures.length > (p.maxCaptures ?? 80) ||
    !Number.isFinite(Date.parse(r.createdAt))
  )
    throw Error("Invalid recording.");
  if (
    r.outcome !== undefined &&
    !["running", "passed", "failed"].includes(r.outcome)
  )
    throw Error("Invalid recording outcome.");
  if (r.schemaVersion !== undefined && r.schemaVersion !== 1)
    throw Error("Unsupported recording version.");
  const definition = r.definition ?? w;
  if (
    definition.id !== r.workflow ||
    !Array.isArray(definition.nodes) ||
    definition.nodes.length > 500 ||
    !Array.isArray(definition.edges) ||
    definition.edges.length > 2000 ||
    !Array.isArray(definition.route)
  )
    throw Error("Invalid recording definition.");
  layout(definition);
  if (definition.route.some((id) => !definition.nodes.some((n) => n.id === id)))
    throw Error("Invalid recording route.");
  let previous = -1;
  for (const c of r.captures) {
    const n = definition.nodes.find((n) => n.id === c.stepId);
    if (
      !n ||
      c.surface !== n.surface ||
      !Number.isFinite(c.at) ||
      c.at < 0 ||
      c.at < previous ||
      c.at > (p.maxDuration ?? 86400000) ||
      typeof c.html !== "string" ||
      c.html.length > (p.maxHtml ?? 3000000) ||
      typeof c.heading !== "string" ||
      c.heading.length > 180 ||
      typeof c.url !== "string"
    )
      throw Error("Invalid capture.");
    previous = c.at;
    const u = new URL(c.url);
    if (!p.origins(r.workflow).includes(u.origin) || u.search || u.hash)
      throw Error("Unsupported capture URL.");
    if (
      c.guide &&
      (typeof c.guide.caption !== "string" ||
        !["inspect", "click", "fill"].includes(c.guide.action))
    )
      throw Error("Invalid capture guide.");
  }
  if (JSON.stringify(r).length > (p.maxBytes ?? 30000000))
    throw Error("Recording too large.");
  return r;
}
