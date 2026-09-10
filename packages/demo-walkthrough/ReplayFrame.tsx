import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { Capture, PlaybackArtifact } from "./contracts";

// Keep the painted slide mounted while its replacement loads underneath it.
export function ReplayFrame({
  capture,
  artifacts = [],
  artifactTime = 0,
  title,
  active,
  onFocus,
  onTakeover,
  prepareSnapshot,
}: {
  artifacts?: PlaybackArtifact[];
  artifactTime?: number;
  onTakeover?: () => void;
  prepareSnapshot: (capture: Capture) => string;
  capture: Capture;
  title: string;
  active: boolean;
  onFocus: (x: number, y: number) => void;
}) {
  const [takeover, setTakeover] = useState(false);
  const maskId = useId().replace(/:/g, "");
  const html = useMemo(
    () => prepareSnapshot(capture),
    [capture, prepareSnapshot],
  );
  const [rect, setRect] = useState<{
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);
  const buffer = useRef<HTMLDivElement>(null);
  const measure = (frame: HTMLIFrameElement, scroll = false) => {
    const target = frame.contentDocument?.querySelector<HTMLElement>(
      "[data-player-focus]",
    );
    if (!target) return null;
    if (scroll)
      target.scrollIntoView({
        block: "center",
        inline: "nearest",
        behavior: "instant",
      });
    const r = target.getBoundingClientRect();
    return {
      x: r.x - 8,
      y: r.y - 8,
      width: r.width + 16,
      height: r.height + 16,
    };
  };
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      const frame = buffer.current?.querySelector<HTMLIFrameElement>(
        'iframe[aria-hidden="false"]',
      );
      if (frame) setRect(measure(frame, true));
    });
    if (buffer.current) observer.observe(buffer.current);
    return () => observer.disconnect();
  }, []);
  const [painted, setPainted] = useState<string | null>(null);
  useEffect(() => {
    const bounds = buffer.current?.getBoundingClientRect();
    if (active && rect && bounds?.width)
      onFocus(
        bounds.x + rect.x + rect.width * 0.65,
        bounds.y + rect.y + rect.height * 0.8,
      );
  }, [active, rect, painted, onFocus]);
  const latest = useRef(html);
  latest.current = html;
  const pendingFrames = useRef<number[]>([]);
  useEffect(
    () => () => pendingFrames.current.forEach(cancelAnimationFrame),
    [],
  );
  useEffect(() => { setTakeover(false); }, [html]);
  const returnToFrame = () => {
    setTakeover(false);
    const frame = buffer.current?.querySelector<HTMLIFrameElement>('iframe[aria-hidden="false"]');
    if (frame) setRect(measure(frame, true));
  };
  const event = capture.artifact;
  const progress = Math.min(1, artifactTime / 1000);
  const trayX = Math.max(0, (buffer.current?.clientWidth ?? 600) - 280);
  const originX = rect ? Math.max(0, Math.min(rect.x, trayX)) : trayX;
  const originY = rect ? Math.max(0, rect.y) : 60;
  const fraction = event?.action === "use" ? 1 - progress : progress;
  const documents = painted && painted !== html ? [painted, html] : [html];
  return (
    <div ref={buffer} className="wp-replay-buffer" aria-busy={painted !== html} onWheelCapture={event => {
      if (!takeover) return;
      event.stopPropagation();
      buffer.current?.querySelector<HTMLIFrameElement>('iframe[aria-hidden="false"]')?.contentWindow?.scrollBy(event.deltaX, event.deltaY);
    }}>
      {documents.map((document) => (
        <iframe
          key={document}
          title={title + (document === painted ? "" : " loading")}
          sandbox="allow-same-origin"
          srcDoc={document}
          aria-hidden={document !== painted}
          tabIndex={takeover && document === painted ? 0 : -1}
          // Replay is a fixed slide. Wheel/touch input belongs to the outer viewer,
          // otherwise the captured document scrolls independently of its spotlight.
          style={{ visibility: document === painted ? "visible" : "hidden", pointerEvents: "none" }}
          onLoad={(event) => {
            const frame = event.currentTarget;
            measure(frame, true);
            pendingFrames.current.push(
              requestAnimationFrame(() => {
                pendingFrames.current.push(
                  requestAnimationFrame(() => {
                    if (latest.current === document) {
                      setRect(measure(frame));
                      setPainted(document);
                    }
                  }),
                );
              }),
            );
          }}
        />
      ))}
      {!takeover && artifacts.length > 0 && <aside className="wp-file-tray" aria-label="Downloaded files in this walkthrough">
        <small>Downloaded files · demo</small>
        {artifacts.map(file => <div key={file.id}>▤ {file.name}</div>)}
      </aside>}
      {!takeover && event && rect && artifactTime < 1300 && <div className="wp-file-flight" aria-label={event.action === "use" ? "Using downloaded file" : "Downloading file"} style={{left:originX + (trayX-originX)*fraction, top:originY + (64-originY)*fraction, opacity:event.action === "use" && progress === 1 ? 0 : 1}}>▤ {event.name}</div>}
      <button type="button" className="wp-takeover" aria-pressed={takeover} onClick={() => takeover ? returnToFrame() : (onTakeover?.(), setTakeover(true))}>
        {takeover ? "Return to frame" : "Take over"}
      </button>
      {!takeover && rect && (
        <svg
          className="wp-spotlight"
          width="100%"
          height="100%"
          aria-hidden="true"
        >
          <defs>
            <mask id={maskId}>
              <rect width="100%" height="100%" fill="white" />
              <rect
                x={rect.x}
                y={rect.y}
                width={rect.width}
                height={rect.height}
                rx="8"
                fill="black"
              />
            </mask>
          </defs>
          <rect
            width="100%"
            height="100%"
            fill="rgba(0,0,0,0.5)"
            mask={`url(#${maskId})`}
          />
          <rect
            x={rect.x}
            y={rect.y}
            width={rect.width}
            height={rect.height}
            rx="8"
            fill="none"
            stroke="#b9ed72"
            strokeWidth="3"
          />
        </svg>
      )}
    </div>
  );
}
