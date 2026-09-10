export type SnapshotPolicy = {
  assetOrigins?: string[];
  resolveLegacyTarget?: (doc: Document) => Element | null;
};
export function prepareReplaySnapshot(
  html: string,
  policy: SnapshotPolicy = {},
) {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const target =
    doc.querySelector("[data-player-focus]") ??
    policy.resolveLegacyTarget?.(doc);
  doc
    .querySelectorAll("[data-player-focus]")
    .forEach((e) => e.removeAttribute("data-player-focus"));
  target?.setAttribute("data-player-focus", "true");
  doc
    .querySelectorAll("script,iframe,object,embed,base,meta,link")
    .forEach((e) => e.remove());
  doc.querySelectorAll("*").forEach((e) => {
    for (const a of [...e.attributes])
      if (
        a.name.startsWith("on") ||
        ["srcdoc", "action", "formaction", "href", "target", "srcset"].includes(
          a.name,
        )
      )
        e.removeAttribute(a.name);
  });
  const origins = (policy.assetOrigins ?? [])
    .map((o) => new URL(o).origin)
    .join(" ");
  const meta = doc.createElement("meta");
  meta.httpEquiv = "Content-Security-Policy";
  meta.content = `default-src 'none'; style-src 'unsafe-inline'; img-src data: ${origins}; font-src data: ${origins}; form-action 'none'; base-uri 'none'`;
  doc.head.prepend(meta);
  const style = doc.createElement("style");
  style.textContent =
    '*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}[style*="--visual-viewport"]{--visual-viewport-height:100dvh!important;--visual-viewport-width:100vw!important}body{top:0!important}*{scrollbar-width:none!important}*::-webkit-scrollbar{display:none!important}';
  doc.head.append(style);
  return doc.documentElement.outerHTML;
}
export function guidedSnapshot(html: string, selector?: string) {
  return prepareReplaySnapshot(html, {
    resolveLegacyTarget: (doc) => {
      try {
        return selector ? doc.querySelector(selector) : null;
      } catch {
        return null;
      }
    },
  });
}
