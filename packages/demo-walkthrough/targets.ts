import { useCallback } from "react";
/** Stable target IDs work in portals and do not depend on text or CSS classes. */
export function useDemoTarget(id: string) {
  return useCallback(
    (element: HTMLElement | null) => {
      if (element) element.dataset.demoTarget = id;
    },
    [id],
  );
}
export function findDemoTarget(doc: Document, id: string) {
  return (
    [...doc.querySelectorAll<HTMLElement>("[data-demo-target]")].find(
      (el) => el.dataset.demoTarget === id,
    ) || null
  );
}
export function measureDemoTarget(element: Element) {
  const r = element.getBoundingClientRect();
  return {
    x: r.x + r.width * 0.65,
    y: r.y + r.height * 0.8,
    rect: { x: r.x, y: r.y, width: r.width, height: r.height },
  };
}
/** Convert child CSS pixels to parent CSS pixels, including iframe scaling. */
export function framePoint(
  frame: HTMLIFrameElement,
  point: { x: number; y: number },
  viewport: { width: number; height: number },
) {
  const r = frame.getBoundingClientRect();
  return {
    x: r.x + (point.x * r.width) / viewport.width,
    y: r.y + (point.y * r.height) / viewport.height,
  };
}
export function observeDemoTarget(
  element: HTMLElement,
  onChange: ReturnType<typeof measureDemoTarget> extends infer T
    ? (value: T) => void
    : never,
) {
  const update = () => onChange(measureDemoTarget(element));
  const resize = new ResizeObserver(update);
  resize.observe(element);
  const win = element.ownerDocument.defaultView!;
  win.addEventListener("scroll", update, true);
  win.addEventListener("resize", update);
  update();
  return () => {
    resize.disconnect();
    win.removeEventListener("scroll", update, true);
    win.removeEventListener("resize", update);
  };
}
