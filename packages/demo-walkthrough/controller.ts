import { useCallback, useEffect, useRef, useState } from "react";
import type { StudioAdapter } from "./adapter";
import type {
  Capture,
  Recording,
  StudioController,
  Workflow,
} from "./contracts";
import {
  layout,
  clock,
  workflowPlayback,
  recordingProgress,
  latestRecording,
} from "./model";
import { framePoint } from "./targets";
import { connectFrame, framePrefix, protocol } from "./transport";
import { runWalkthrough } from "./runner";
const errorMessage = (e: unknown) =>
  e instanceof Error ? e.message : String(e);
export function useDemoStudio(adapter: StudioAdapter): StudioController {
  const [initial] = useState(() => {
    const q = adapter.navigation?.read() ?? {};
    const workflow =
      adapter.workflows.find((w) => w.id === q.workflow) ??
      adapter.workflows[0];
    if (!workflow) throw Error("At least one workflow is required.");
    return {
      workflow,
      actor:
        q.actor === "all" || adapter.actors.some((a) => a.id === q.actor)
          ? q.actor!
          : (workflow.defaultActor ?? adapter.actors[0]?.id ?? "all"),
      recording: q.recording,
    };
  });
  const [workflow, setWorkflow] = useState(initial.workflow),
    [actor, setActor] = useState(initial.actor);
  const actorFor = (w: Workflow, id: string) =>
    w.nodes.find((n) => n.id === id)?.actor ??
    w.defaultActor ??
    adapter.actors[0]?.id ??
    "all";
  const firstFor = (w: Workflow, a: string) =>
    w.nodes.find((n) => a === "all" || actorFor(w, n.id) === a) ?? w.nodes[0];
  const [selected, setSelected] = useState(
    firstFor(initial.workflow, initial.actor).id,
  );
  const [recordings, setRecordings] = useState<Recording[]>([]),
    [recording, setRecording] = useState<Recording | null>(null);
  const [mode, setMode] = useState<"live" | "replay">("live"),
    [time, setTime] = useState(0),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1),
    [zoom, setZoom] = useState(0.8);
  const [busy, setBusy] = useState(false),
    [running, setRunning] = useState(false),
    [error, setError] = useState(""),
    [enabled, setEnabled] = useState(false),
    [guideState, setGuideState] = useState("");
  const [fixture, setFixture] = useState<Record<string, string> | null>(null),
    [subtitles, setSubtitles] = useState(
      () => adapter.preferences?.read() ?? true,
    );
  const [branch, setBranch] = useState("all"),
    [libraryOpen, setLibraryOpen] = useState(false),
    [reviewView, setReviewView] = useState<"timeline" | "map">("timeline");
  const stage = useRef<HTMLDivElement>(null),
    reviewPane = useRef<HTMLDivElement>(null),
    frames = useRef<Record<string, HTMLIFrameElement | null>>({}),
    stopRun = useRef(false),
    nonce = useRef(crypto.randomUUID());
  const lifecycle = useRef(new AbortController()),
    runAbort = useRef<AbortController | null>(null),
    [cursor, setCursor] = useState({ x: 32, y: 64 });
  const surfaces = adapter.surfaces.map((s) => s.id),
    names = Object.fromEntries(adapter.surfaces.map((s) => [s.id, s.label]));
  const defaults = () =>
    Object.fromEntries(adapter.surfaces.map((s) => [s.id, s.initialPath]));
  const [paths, setPaths] = useState(() => {
    const n = firstFor(initial.workflow, initial.actor);
    return { ...defaults(), ...(n.path ? { [n.surface]: n.path } : {}) };
  });
  const frameUrl = (s: string, path: string, n: string) => {
    const definition = adapter.surfaces.find((x) => x.id === s);
    if (!definition) throw Error("Unknown surface");
    const u = new URL(definition.url(path));
    if (!definition.origins.includes(u.origin))
      throw Error("Unsupported frame origin");
    u.searchParams.set("player", n);
    return u.href;
  };
  const effectiveWorkflow =
    mode === "replay" && recording?.definition
      ? recording.definition
      : workflow;
  const node =
    effectiveWorkflow.nodes.find((n) => n.id === selected) ??
    effectiveWorkflow.nodes[0];
  const chapters = effectiveWorkflow.chapters ?? [],
    branches = effectiveWorkflow.branches ?? [],
    captures = recording?.captures ?? [];
  const branchSteps = branches.find((b) => b.id === branch)?.steps;
  const playback = workflowPlayback(
    branch !== "all" && branchSteps
      ? captures.filter((c) => branchSteps.includes(c.stepId))
      : captures,
    effectiveWorkflow,
  );
  const duration = playback.length ? playback.at(-1)!.playAt + 3000 : 0,
    active = playback.filter((c) => c.playAt <= time).at(-1),
    activeCaptureAt = active?.playAt;
  const stepActor = actorFor(effectiveWorkflow, node.id),
    handoff = actor !== "all" && actor !== stepActor;
  const journeys =
    actor === "all"
      ? adapter.workflows
      : adapter.workflows.filter((w) =>
          w.nodes.some((n) => actorFor(w, n.id) === actor),
        );
  const graph = layout(effectiveWorkflow),
    width = Math.max(0, ...graph.map((n) => n.x)) + 180,
    height = Math.max(0, ...graph.map((n) => n.y)) + 90;
  const moveCursor = useCallback((x: number, y: number) => {
    const r = stage.current?.getBoundingClientRect();
    if (!r) return;
    const next = {
      x: Math.max(2, Math.min(r.width - 22, x - r.x)),
      y: Math.max(2, Math.min(r.height - 29, y - r.y)),
    };
    setCursor((old) => (old.x === next.x && old.y === next.y ? old : next));
  }, []);
  useEffect(() => {
    const receive = (e: MessageEvent) => {
      if (
        e.data?.protocol !== protocol ||
        e.data.type !== "focus" ||
        e.data.nonce !== nonce.current
      )
        return;
      const surface = adapter.surfaces.find(
        (s) =>
          frames.current[s.id]?.contentWindow === e.source &&
          s.origins.includes(e.origin),
      );
      if (!surface || !e.data.viewport || !e.data.focus) return;
      const point = framePoint(
        frames.current[surface.id]!,
        e.data.focus,
        e.data.viewport,
      );
      moveCursor(point.x, point.y);
    };
    window.addEventListener("message", receive);
    return () => window.removeEventListener("message", receive);
  }, [adapter, moveCursor]);
  const writeNavigation = (w: Workflow, a: string, r?: Recording | null) =>
    adapter.navigation?.write({ workflow: w.id, actor: a, recording: r?.id });
  useEffect(() => {
    let alive = true;
    lifecycle.current = new AbortController();
    adapter.store
      .list()
      .then((runs) => {
        if (!alive) return;
        setEnabled(true);
        setRecordings(runs);
        const r =
          (!initial.recording || initial.recording === "latest")
            ? latestRecording(runs, initial.workflow)
            : runs.find(
                (r) =>
                  r.id === initial.recording &&
                  r.workflow === initial.workflow.id,
              ) ?? latestRecording(runs, initial.workflow);
        if (r) {
          writeNavigation(initial.workflow, initial.actor, r);
          setRecording(r);
          setMode("replay");
          const w = r.definition ?? initial.workflow;
          setTime(
            workflowPlayback(r.captures, w).find(
              (c) =>
                initial.actor === "all" ||
                actorFor(w, c.stepId) === initial.actor,
            )?.playAt ?? 0,
          );
        }
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e));
      });
    return () => {
      alive = false;
      lifecycle.current.abort();
      runAbort.current?.abort();
      stopRun.current = true;
    };
  }, [adapter]);
  useEffect(() => {
    if (!playing || mode !== "replay") return;
    let last = performance.now();
    const timer = setInterval(() => {
      const now = performance.now();
      const elapsed = Math.max(0, now - last);
      last = now;
      setTime((v) => Math.min(duration, v + elapsed * speed));
    }, 100);
    return () => clearInterval(timer);
  }, [playing, mode, duration, speed]);
  useEffect(() => {
    if (time >= duration) setPlaying(false);
  }, [time, duration]);
  useEffect(() => {
    if (mode === "replay" && active) setSelected(active.stepId);
  }, [mode, active?.stepId]);
  useEffect(() => {
    reviewPane.current
      ?.querySelector('[aria-label="Captured frames"] [aria-pressed="true"]')
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [activeCaptureAt, reviewView]);
  const rpc = async (
    surface: string,
    type: string,
    key?: string,
    context: Record<string, string> = {},
  ) => {
    const frame = frames.current[surface];
    if (!frame) throw Error("Frame is not mounted.");
    const origin = new URL(frame.src).origin;
    const definition = adapter.surfaces.find((s) => s.id === surface);
    if (!definition?.origins.includes(origin))
      throw Error("Unsupported frame origin");
    return connectFrame(
      {
        frame,
        origin,
        nonce: nonce.current,
        signal: runAbort.current?.signal ?? lifecycle.current.signal,
        focus: moveCursor,
      },
      type,
      key,
      context,
    );
  };
  useEffect(() => {
    if (mode !== "live" || running) return;
    let disposed = false,
      waiting = false;
    const poll = async () => {
      if (waiting) return;
      waiting = true;
      try {
        const r = await rpc(
          node.surface,
          "guide",
          workflow.id + "/" + selected,
          fixture ?? {},
        );
        if (!disposed) setGuideState(r.ok ? "Target found" : r.error);
      } catch {
        if (!disposed) setGuideState("Waiting for the target page…");
      } finally {
        waiting = false;
      }
    };
    void poll();
    const timer = setInterval(poll, 1500);
    return () => {
      disposed = true;
      clearInterval(timer);
    };
  }, [selected, workflow.id, mode, running, fixture]);
  const save = async (r: Recording) => {
    await adapter.store.save(r);
    if (lifecycle.current.signal.aborted) return;
    setRecording({ ...r, captures: [...r.captures] });
    setRecordings((old) => [r, ...old.filter((x) => x.id !== r.id)]);
  };
  async function record() {
    setBranch("all");
    setRunning(true);
    setPlaying(false);
    setMode("live");
    setRecording(null);
    setTime(0);
    setError("");
    setSubtitles(true);
    stopRun.current = false;
    runAbort.current = new AbortController();
    try {
      await runWalkthrough({
        workflow,
        plan: adapter.plan(workflow),
        signal: runAbort.current.signal,
        stopped: () => stopRun.current,
        prepare: setFixture,
        select: (id, surface, path) => {
          setSelected(id);
          if (path) setPaths((p) => ({ ...p, [surface]: path }));
        },
        rpc,
        save,
      });
      setMode("replay");
      setTime(0);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      runAbort.current = null;
      setRunning(false);
    }
  }
  const defaultActor = (id: string) =>
    adapter.workflows.find((w) => w.id === id)?.defaultActor ??
    adapter.actors[0]?.id ??
    "all";
  function chooseWorkflow(id: string, perspective = actor) {
    const w = adapter.workflows.find((w) => w.id === id);
    if (!w) return;
    const r = latestRecording(recordings, w),
      ew = r?.definition ?? w,
      n = firstFor(ew, perspective);
    setWorkflow(w);
    setActor(perspective);
    setSelected(n.id);
    setRecording(r ?? null);
    setPlaying(false);
    setMode(r ? "replay" : "live");
    setBranch("all");
    setError("");
    setGuideState("");
    setTime(
      r
        ? (workflowPlayback(r.captures, ew).find((c) => c.stepId === n.id)
            ?.playAt ?? 0)
        : 0,
    );
    setPaths({ ...defaults(), ...(n.path ? { [n.surface]: n.path } : {}) });
    writeNavigation(w, perspective, r);
  }
  function chooseActor(next: string) {
    setActor(next);
    setPlaying(false);
    setBranch("all");
    const choices =
      next === "all"
        ? adapter.workflows
        : adapter.workflows.filter((w) =>
            w.nodes.some((n) => actorFor(w, n.id) === next),
          );
    if (choices.length)
      chooseWorkflow(
        choices.find((w) => w.id === workflow.id)?.id ?? choices[0].id,
        next,
      );
    else writeNavigation(workflow, next, recording);
  }
  function select(id: string) {
    setPlaying(false);
    setSelected(id);
    if (mode === "replay") {
      const all = workflowPlayback(captures, effectiveWorkflow);
      const c =
        playback.find((c) => c.stepId === id) ??
        all.find((c) => c.stepId === id);
      if (!playback.some((c) => c.stepId === id)) setBranch("all");
      if (c) setTime(c.playAt);
    } else {
      const n = workflow.nodes.find((n) => n.id === id);
      if (n?.path) setPaths((p) => ({ ...p, [n.surface]: n.path }));
    }
  }
  function fresh() {
    setPlaying(false);
    setMode("live");
    setRecording(null);
    setFixture(null);
    setTime(0);
    setBranch("all");
    const n = firstFor(workflow, actor);
    setSelected(n.id);
    setPaths({ ...defaults(), ...(n.path ? { [n.surface]: n.path } : {}) });
    writeNavigation(workflow, actor);
  }
  return {
    cancelRun: () => {
      stopRun.current = true;
      runAbort.current?.abort();
    },
    libraryOpen,
    reviewView,
    actor,
    busy,
    running,
    chooseActor,
    actors: adapter.actors,
    journeys,
    workflow: effectiveWorkflow,
    chooseWorkflow,
    journeyTitle: (id, a, fallback) =>
      adapter.workflows.find((w) => w.id === id)?.titles?.[a] ?? fallback,
    setLibraryOpen,
    setReviewView,
    recordings,
    setRecording,
    setMode,
    setPlaying,
    setTime,
    recordingProgress,
    clock,
    enabled,
    setActor,
    stopRun,
    defaultActor,
    fresh,
    names,
    node,
    stage,
    surfaces,
    playback,
    time,
    handoff,
    actorName: (id) =>
      id === "all"
        ? "Complete process"
        : (adapter.actors.find((a) => a.id === id)?.label ?? id),
    stepActor,
    mode,
    nonce,
    frames,
    frameUrl,
    paths,
    moveCursor,
    subtitles,
    guideFor: (w, s) =>
      mode === "replay" && active?.guide ? active.guide : adapter.guide(w, s)!,
    selected,
    crossHandoff: () => {
      setActor(stepActor);
      setPlaying(false);
      writeNavigation(workflow, stepActor, recording);
    },
    cursor,
    recording,
    activeCaptureAt,
    playing,
    duration,
    setSubtitles,
    speed,
    setSpeed,
    captures,
    reviewPane,
    activeChapter: chapters.find((c) => c.steps.includes(selected)),
    branch,
    setBranch,
    guideState,
    fixture,
    details: fixture ? (adapter.details?.(fixture) ?? []) : [],
    error,
    setZoom,
    width,
    zoom,
    height,
    graph,
    select,
    chapters,
    branches,
    record,
    frameName: (n) => framePrefix + n,
    displayAddress: adapter.displayAddress,
    prepareSnapshot: adapter.prepareSnapshot,
    saveSubtitles: (e) => adapter.preferences?.write(e),
  };
}
