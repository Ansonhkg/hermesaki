import {
  Button,
  Slider,
  Play,
  Pause,
  ForwardStep,
  ArrowRotateLeft,
  Text,
} from "./controls";
import { ReplayFrame } from "./ReplayFrame";
import { useDemoWalkthrough } from "./provider";
import type { Perspective } from "./contracts";
import "./style.css";
export * from "./provider";
export type * from "./contracts";
export function DemoWalkthroughStudio() {
  const {
        actor,
    busy,
    enabled,
    running,
    chooseActor,
    actors,
    journeys,
    workflow,
    chooseWorkflow,
    journeyTitle,
          setMode,
    setPlaying,
    setTime,
    recordingProgress,
    clock,
              names,
    node,
    stage,
    surfaces,
    playback,
    time,
    actorName,
    stepActor,
    mode,
    nonce,
    frames,
    frameUrl,
    paths,
    moveCursor,
    subtitles,
    guideFor,
    selected,
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
          guideState,
      details,
    error,
    setZoom,
    width,
    zoom,
    height,
    graph,
    select,
          frameName,
    prepareSnapshot,
    saveSubtitles,
  } = useDemoWalkthrough();
  return (
    <div className="demo-walkthrough-root">
      <div
        className="workflow-player"
        data-library="false"
        data-review="map"
      >
        <header className="wp-heading">
          <div>
            <h1 className="wp-brand"><img src={new URL("./logo.png", import.meta.url).href} alt="Demo Walkthrough" width="36" height="36" /></h1>
            <label className="wp-workflow-picker">
              Perspective
              <select
                aria-label="Perspective"
                value={actor}
                disabled={busy || running}
                onChange={(e) => chooseActor(e.target.value as Perspective)}
              >
                {actors.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label}
                  </option>
                ))}
                <option value="all">Complete process</option>
              </select>
            </label>
            <label className="wp-workflow-picker">
              Journey{" "}
              <select
                aria-label="Select journey"
                value={journeys.length ? workflow.id : ""}
                disabled={busy || running || !journeys.length}
                onChange={(e) => chooseWorkflow(e.target.value)}
              >
                {!journeys.length && (
                  <option value="">No journeys mapped yet</option>
                )}
                {journeys.map((w) => (
                  <option key={w.id} value={w.id}>
                    {journeyTitle(w.id, actor, w.title)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </header>
        <div className="wp-layout">
          {!journeys.length ? (
            <section className="wp-actor-empty">
              <h2>{actorName(actor)} journeys</h2>
              <p>
                No journeys have been mapped for this perspective yet.
              </p>
            </section>
          ) : (
            <section className="wp-workspace">
              <p className="wp-note" aria-live="polite">
                Now showing {names[node.surface]} · {node.label}
              </p>
              <div ref={stage} className="wp-stage">
                {surfaces.map((s) => {
                  const c = [...playback]
                    .reverse()
                    .find((c) => c.surface === s && c.playAt <= time);
                  return (
                    <section
                      className={
                        "wp-frame " +
                        (s === node.surface ? "wp-frame-active" : "")
                      }
                      key={s}
                      hidden={s !== node.surface}
                    >
                      <header>
                        <strong>
                          {actorName(stepActor)} · {names[s]}
                        </strong>
                        <small>
                          {mode === "live"
                            ? "Live · Guided focus"
                            : "Replay · Guided focus"}
                        </small>
                      </header>
                      <div className="wp-address">
                        {new URL(frameUrl(s, paths[s], nonce.current)).host}
                      </div>
                      {mode === "live" && enabled ? (
                        <iframe
                          key={"live-" + s}
                          name={frameName(nonce.current)}
                          title={names[s]}
                          ref={(el) => {
                            frames.current[s] = el;
                          }}
                          src={frameUrl(s, paths[s], nonce.current)}
                          sandbox="allow-scripts allow-same-origin allow-forms allow-modals"
                        />
                      ) : c ? (
                        <ReplayFrame
                          prepareSnapshot={prepareSnapshot}
                          capture={c}
                          title={names[s] + " recorded frame"}
                          active={s === node.surface}
                          onFocus={moveCursor}
                        />
                      ) : (
                        <div className="wp-frame-empty">
                          {enabled
                            ? "No frame captured at this time."
                            : "Loading development player…"}
                        </div>
                      )}
                      {subtitles && (
                        <div
                          className="wp-subtitles"
                          role="status"
                          aria-live="polite"
                          aria-atomic="true"
                        >
                          <p>
                            {guideFor(workflow.id, selected)?.caption ||
                              "This scenario is not implemented yet. No action or result is being demonstrated."}
                          </p>
                        </div>
                      )}
                    </section>
                  );
                })}
                <div
                  className="wp-persistent-cursor"
                  aria-hidden="true"
                  style={{
                    transform: `translate3d(${cursor.x}px,${cursor.y}px,0)`,
                  }}
                >
                  {mode === "replay" &&
                    playback.find((c) => c.playAt === activeCaptureAt)
                      ?.click === true && (
                      <span
                        key={`${recording?.id}:${activeCaptureAt}`}
                        className="wp-click-pulse"
                      />
                    )}
                  <svg
                    key={
                      mode === "replay"
                        ? `${recording?.id}:${activeCaptureAt}`
                        : "live"
                    }
                    className={
                      mode === "replay" &&
                      playback.find((c) => c.playAt === activeCaptureAt)
                        ?.click === true
                        ? "wp-cursor-clicking"
                        : ""
                    }
                    width="22"
                    height="29"
                    viewBox="0 0 32 42"
                  >
                    <path
                      d="M2 2L2 34L10 27L17 39L24 35L17 23L29 22Z"
                      fill="#101510"
                      stroke="white"
                      strokeWidth="2"
                    />
                  </svg>
                </div>
              </div>
              <div className="wp-controls">
                <Button
                  isIconOnly
                  aria-label={playing ? "Pause" : "Play"}
                  isDisabled={mode !== "replay" || !duration}
                  onPress={() => {
                    if (time >= duration) setTime(0);
                    setPlaying((v) => !v);
                  }}
                >
                  {playing ? (
                    <Pause aria-hidden="true" />
                  ) : (
                    <Play aria-hidden="true" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  isIconOnly
                  aria-label="Next capture"
                  isDisabled={
                    mode !== "replay" || !playback.some((c) => c.playAt > time)
                  }
                  onPress={() => {
                    setPlaying(false);
                    setTime(
                      playback.find((c) => c.playAt > time)?.playAt || duration,
                    );
                  }}
                >
                  <ForwardStep aria-hidden="true" />
                </Button>
                <strong className="wp-clock">
                  {clock(time)} / {clock(duration)}
                </strong>
                <Slider
                  aria-label="Playback time"
                  minValue={0}
                  maxValue={Math.max(duration, 1)}
                  step={1}
                  value={time}
                  isDisabled={mode !== "replay"}
                  onChange={(v) => {
                    setPlaying(false);
                    setTime(Number(v));
                  }}
                >
                  <Slider.Track>
                    <Slider.Fill />
                    <Slider.Thumb />
                  </Slider.Track>
                </Slider>
                <Button
                  variant="ghost"
                  isIconOnly
                  aria-label={subtitles ? "Hide subtitles" : "Show subtitles"}
                  aria-pressed={subtitles}
                  onPress={() => {
                    setSubtitles(!subtitles);
                    saveSubtitles(!subtitles);
                  }}
                >
                  <Text aria-hidden="true" />
                </Button>
                <label>
                  Speed{" "}
                  <select
                    value={speed}
                    onChange={(e) => setSpeed(Number(e.target.value))}
                  >
                    {[0.5, 1, 1.5, 2].map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
                <Button
                  variant="secondary"
                  isIconOnly
                  aria-label="Replay recording"
                  isDisabled={!captures.length || busy || running}
                  onPress={() => {
                    setMode("replay");
                    setTime(0);
                    setPlaying(true);
                  }}
                >
                  <ArrowRotateLeft aria-hidden="true" />
                </Button>
              </div>
              <div
                ref={reviewPane}
                className="wp-review"
                aria-label="Workflow review"
              >
                {recording &&
                  (() => {
                    const progress = recordingProgress(recording, workflow);
                    return (
                      <p role="status" className="wp-hint">
                        <strong>
                          {running ? "Recording" : progress.label} ·{" "}
                          {progress.count}/{progress.total} steps captured.
                        </strong>
                        {!progress.complete &&
                          !running &&
                          ` This is not the end of the workflow.${progress.next ? ` Next uncaptured step: ${progress.next}.` : ""} Run it again to capture the complete journey.`}
                      </p>
                    );
                  })()}
                <p className="wp-note">
                  {mode === "live"
                    ? "Live preview. An agent can prepare a walkthrough for this journey. The workflow map is available to review now."
                    : `${captures.length} captured frames · Each capture held for review · Original recording ${clock(captures.at(-1)?.at || 0)}. Only captured states are available, not continuous video.`}
                </p>
                {guideState && mode === "live" && (
                  <p role="status">{guideState}</p>
                )}
                {details.length > 0 && (
                  <details>
                    <summary>Run details</summary>
                    {details.map((d) => (
                      <p key={d.label}>
                        <strong>{d.label}</strong>: <code>{d.value}</code>
                      </p>
                    ))}
                  </details>
                )}
                {(error || recording?.error) && (
                  <p role="alert">{error || recording?.error}</p>
                )}
                <div className="wp-bottom">
                  <section className="wp-map">
                    <header className="wp-row">
                      <div>
                        <h3>Workflow map</h3>
                        <small>
                          Forks, nested paths and joins · Click a step to
                          inspect
                        </small>
                      </div>
                      <div>
                        <Button
                          variant="ghost"
                          aria-label="Zoom out"
                          onPress={() =>
                            setZoom((z) => Math.max(0.35, z - 0.1))
                          }
                        >
                          −
                        </Button>
                        <Button variant="ghost" onPress={() => setZoom(0.8)}>
                          Reset zoom
                        </Button>
                        <Button
                          variant="ghost"
                          aria-label="Zoom in"
                          onPress={() => setZoom((z) => Math.min(1.5, z + 0.1))}
                        >
                          +
                        </Button>
                      </div>
                    </header>
                    <div className="wp-graph-scroll">
                      <div
                        style={{ width: width * zoom, height: height * zoom }}
                      >
                        <div
                          className="wp-graph"
                          style={{ width, height, transform: `scale(${zoom})` }}
                        >
                          <svg width={width} height={height} aria-hidden="true">
                            <defs>
                              <marker
                                id="wp-arrow"
                                markerWidth="8"
                                markerHeight="8"
                                refX="7"
                                refY="3"
                                orient="auto"
                              >
                                <path
                                  d="M0,0 L0,6 L7,3 z"
                                  fill="currentColor"
                                />
                              </marker>
                            </defs>
                            {workflow.edges.map(([a, b]) => {
                              const from = graph.find((n) => n.id === a)!,
                                to = graph.find((n) => n.id === b)!;
                              return (
                                <path
                                  key={a + b}
                                  d={`M${from.x + 155},${from.y + 30} H${from.x + 172} V${to.y + 30} H${to.x}`}
                                  markerEnd="url(#wp-arrow)"
                                />
                              );
                            })}
                          </svg>
                          {graph.map((n) => (
                            <button
                              key={n.id}
                              className={
                                "wp-node " +
                                (selected === n.id ? "selected" : "")
                              }
                              style={{ left: n.x, top: n.y }}
                              disabled={running}
                              onClick={() => select(n.id)}
                              aria-pressed={selected === n.id}
                            >
                              <strong>{n.label}</strong>
                              <small>
                                {captures.some(
                                  (c) => c.stepId === n.id && c.verified,
                                )
                                  ? "Checked"
                                  : captures.some((c) => c.stepId === n.id)
                                    ? "Captured"
                                    : "Not run"}{" "}
                                · {names[n.surface]}
                              </small>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

export * from "./targets";

export { useDemoStudio } from "./controller";
export type { StudioAdapter } from "./adapter";

import { useDemoStudio as useStudioController } from "./controller";
import { DemoWalkthroughProvider as StudioProvider } from "./provider";
import type { StudioAdapter } from "./adapter";
export function DemoWalkthrough({ adapter }: { adapter: StudioAdapter }) {
  const controller = useStudioController(adapter);
  return (
    <StudioProvider value={controller}>
      <DemoWalkthroughStudio />
    </StudioProvider>
  );
}
