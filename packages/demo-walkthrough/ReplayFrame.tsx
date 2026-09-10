import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { Capture } from "./contracts";

// Keep the painted slide mounted while its replacement loads underneath it.
export function ReplayFrame({
  capture,
  title,
  active,
  onFocus,
  prepareSnapshot,
}: {
  prepareSnapshot: (capture: Capture) => string;
  capture: Capture;
  title: string;
  active: boolean;
  onFocus: (x: number, y: number) => void;
}) {
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
  const documents = painted && painted !== html ? [painted, html] : [html];
  return (
    <div ref={buffer} className="wp-replay-buffer" aria-busy={painted !== html}>
      {documents.map((document) => (
        <iframe
          key={document}
          title={title + (document === painted ? "" : " loading")}
          sandbox="allow-same-origin"
          srcDoc={document}
          aria-hidden={document !== painted}
          tabIndex={document === painted ? 0 : -1}
          style={{ visibility: document === painted ? "visible" : "hidden" }}
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
      {rect && (
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
