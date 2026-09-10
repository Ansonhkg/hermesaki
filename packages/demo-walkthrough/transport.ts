import { framePoint } from "./targets";
export const protocol = "demo-walkthrough:v1";
export const framePrefix = "demo-walkthrough:";
export function connectFrame(
  options: {
    frame: HTMLIFrameElement;
    origin: string;
    nonce: string;
    signal?: AbortSignal;
    timeout?: number;
    focus?: (x: number, y: number) => void;
  },
  type: string,
  guideKey?: string,
  context: Record<string, string> = {},
) {
  return new Promise<any>((resolve, reject) => {
    const { frame, origin, nonce, signal } = options,
      id = crypto.randomUUID(),
      win = frame.contentWindow;
    if (!win) return reject(Error("Frame is not mounted."));
    let timer: ReturnType<typeof setTimeout>;
    const cleanup = () => {
      clearTimeout(timer);
      window.removeEventListener("message", receive);
      signal?.removeEventListener("abort", abort);
    };
    const abort = () => {
      cleanup();
      reject(Error("Walkthrough stopped."));
    };
    const receive = (e: MessageEvent) => {
      if (
        e.source !== win ||
        e.origin !== origin ||
        e.data?.protocol !== protocol ||
        e.data.nonce !== nonce ||
        e.data.requestId !== id
      )
        return;
      if (!["guided", "captured"].includes(e.data.type)) return;
      cleanup();
      if (e.data.focus && e.data.viewport) {
        const p = framePoint(frame, e.data.focus, e.data.viewport);
        options.focus?.(p.x, p.y);
      }
      if (e.data.error && type === "capture") reject(Error(e.data.error));
      else resolve(e.data);
    };
    timer = setTimeout(() => {
      cleanup();
      reject(Error("Frame did not respond."));
    }, options.timeout ?? 8000);
    window.addEventListener("message", receive);
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) return abort();
    win.postMessage(
      { protocol, type, nonce, requestId: id, guideKey, context },
      origin,
    );
  });
}
