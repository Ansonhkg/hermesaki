import { measureDemoTarget, observeDemoTarget } from "./targets";
import { protocol, framePrefix } from "./transport";
import { interpolate, resolveTarget, type TargetRecipe } from "./bindings";
import { guidanceCss, markTarget } from "./guidance";
export type BridgeOptions = {
  parentOrigin: string;
  enabled: () => Promise<boolean>;
  guides: Record<string, TargetRecipe>;
  authorize: (key: string, context: Record<string, string>) => boolean;
  preserveInput?: (
    live: HTMLInputElement | HTMLTextAreaElement,
    context: Record<string, string>,
  ) => string | undefined;
  captureContext?: (context: Record<string, string>) => Record<string, string>;
};
// Only a dev frame responds, only to its exact operator parent. Only registered development actions are accepted.
export function installDemoBridge(options: BridgeOptions) {
  const { guides, parentOrigin } = options;
  let disposeTarget: (() => void) | undefined;
  const nonce =
    new URLSearchParams(location.search).get("player") ||
    (window.name.startsWith(framePrefix)
      ? window.name.slice(framePrefix.length)
      : "");
  if (!nonce || window.parent === window) return;

  let enabled = false;
  let disposed = false;
  options
    .enabled()
    .then((allowed) => {
      enabled = !disposed && allowed;
      if (!enabled) return;
      const style = document.createElement("style");
      style.id = "player-guidance";
      style.textContent = guidanceCss;
      document.head.append(style);
    })
    .catch(() => {});
  const receive = (event: MessageEvent) => {
    if (
      !enabled ||
      event.source !== window.parent ||
      event.origin !== parentOrigin ||
      event.data?.protocol !== protocol ||
      !["capture", "guide", "perform"].includes(event.data?.type) ||
      event.data.nonce !== nonce
    )
      return;
    const context = event.data.context || {};
    const guide = guides[event.data.guideKey];
    const target = guide ? resolveTarget(document, guide, context) : null;
    if (
      event.data.type === "perform" &&
      (!guide || !options.authorize(event.data.guideKey, context))
    ) {
      window.parent.postMessage(
        {
          protocol,
          type: "guided",
          nonce,
          requestId: event.data.requestId,
          ok: false,
          error: "This action is not authorized.",
        },
        parentOrigin,
      );
      return;
    }
    if (event.data.type !== "capture") {
      const reply = (ok: boolean, error?: string) =>
        window.parent.postMessage(
          {
            protocol,
            type: "guided",
            viewport: { width: innerWidth, height: innerHeight },
            nonce,
            requestId: event.data.requestId,
            ok,
            error,
            url: location.pathname,
            mode: new URLSearchParams(location.search).get("mode"),
            focus: target ? measureDemoTarget(target) : null,
          },
          parentOrigin,
        );
      if (!target || !target.getClientRects().length) {
        reply(false, "The expected element is not visible yet.");
        return;
      }
      document
        .querySelectorAll("[data-player-focus],[data-player-cursor]")
        .forEach((e) => {
          e.removeAttribute("data-player-focus");
          e.removeAttribute("data-player-cursor");
        });
      target.scrollIntoView({ block: "center", behavior: "smooth" });
      markTarget(target);
      disposeTarget?.();
      disposeTarget = observeDemoTarget(target, (focus) =>
        window.parent.postMessage(
          {
            protocol,
            type: "focus",
            nonce,
            focus,
            viewport: { width: innerWidth, height: innerHeight },
          },
          parentOrigin,
        ),
      );
      if (event.data.type === "perform") {
        if (!options.authorize(event.data.guideKey, context)) {
          reply(false, "This action is not authorized.");
          return;
        }
        if (guide.action === "fill") {
          if (!(
            target instanceof HTMLInputElement ||
            target instanceof HTMLTextAreaElement
          )) {
            reply(false, "Expected an input field.");
            return;
          }
          const value = guide.literal
            ? interpolate(guide.literal, context)
            : context[guide.value!];
          if (typeof value !== "string" || value.length > 128) {
            reply(false, "Invalid test value.");
            return;
          }
          Object.getOwnPropertyDescriptor(
            target instanceof HTMLTextAreaElement
              ? HTMLTextAreaElement.prototype
              : HTMLInputElement.prototype,
            "value",
          )!.set!.call(target, value);
          target.dispatchEvent(new Event("input", { bubbles: true }));
          target.dispatchEvent(new Event("change", { bubbles: true }));
          for (const field of guide.fields ?? []) {
            const input = document.querySelector<HTMLInputElement>(
              field.selector,
            );
            if (input) {
              const v = context[field.value];
              if (typeof v !== "string") throw Error("Missing input value");
              Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype,
                "value",
              )!.set!.call(input, v);
              input.dispatchEvent(new Event("input", { bubbles: true }));
              input.dispatchEvent(new Event("change", { bubbles: true }));
            }
          }
        } else if (guide.action === "click") {
          reply(true);
          target.click();
          return;
        }
      }
      reply(true);
      return;
    }
    if (guide && !target) {
      window.parent.postMessage(
        {
          protocol,
          type: "captured",
          nonce,
          requestId: event.data.requestId,
          error: "Target missing; capture was not saved.",
        },
        parentOrigin,
      );
      return;
    }
    const clone = document.documentElement.cloneNode(true) as HTMLElement;
    clone
      .querySelectorAll("[data-player-focus],[data-player-cursor]")
      .forEach((e) => {
        e.removeAttribute("data-player-focus");
        e.removeAttribute("data-player-cursor");
      });
    if (target) {
      const index = [...document.querySelectorAll("*")].indexOf(target);
      (
        [clone, ...clone.querySelectorAll("*")][index] as Element | undefined
      )?.setAttribute("data-player-focus", "true");
    }
    clone.querySelector("#player-guidance")?.remove();
    clone
      .querySelectorAll(
        'script,iframe,object,embed,base,meta,link[rel="preload"],link[rel="modulepreload"]',
      )
      .forEach((e) => e.remove());
    const liveInputs = [
      ...document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>(
        "input,textarea",
      ),
    ];
    clone
      .querySelectorAll<HTMLInputElement | HTMLTextAreaElement>(
        "input,textarea",
      )
      .forEach((e, i) => {
        e.removeAttribute("value");
        e.textContent = "";
        const live = liveInputs[i];
        if (!live) return;
        if (live.type === "password") {
          if (live.value) e.setAttribute("placeholder", "Password entered");
          return;
        }
        const value = options.preserveInput?.(live, context);
        if (value !== undefined) {
          if (e.tagName === "TEXTAREA") e.textContent = value;
          else e.setAttribute("value", value);
        }
      });
    clone.querySelectorAll("*").forEach((e) => {
      for (const a of [...e.attributes])
        if (
          a.name.startsWith("on") ||
          ["srcdoc", "action", "formaction"].includes(a.name)
        )
          e.removeAttribute(a.name);
    });
    clone.querySelectorAll("[href],[src]").forEach((e) => {
      for (const a of ["href", "src"])
        if (e.hasAttribute(a)) {
          try {
            const u = new URL(e.getAttribute(a)!, location.href);
            if (u.origin === location.origin) {
              u.searchParams.delete("player");
              u.searchParams.delete("token");
              e.setAttribute(a, u.href);
            } else e.removeAttribute(a);
          } catch {
            e.removeAttribute(a);
          }
        }
    });
    clone
      .querySelectorAll('link[rel="stylesheet"],style')
      .forEach((e) => e.remove());
    const styles = document.createElement("style");
    styles.textContent = [...document.styleSheets]
      .filter(
        (sheet) => (sheet.ownerNode as HTMLElement)?.id !== "player-guidance",
      )
      .map((sheet) => {
        try {
          return [...sheet.cssRules].map((r) => r.cssText).join("\n");
        } catch {
          return "";
        }
      })
      .join("\n");
    clone.querySelector("head")?.append(styles);
    if (window.scrollY) {
      const offset = document.createElement("style");
      offset.textContent = `body{position:relative;top:-${window.scrollY}px!important}`;
      clone.querySelector("head")?.append(offset);
    }
    const safeUrl = new URL(location.pathname, location.origin).href;
    window.parent.postMessage(
      {
        protocol,
        type: "captured",
        nonce,
        requestId: event.data.requestId,
        html: clone.outerHTML,
        guideKey: guide ? event.data.guideKey : undefined,
        context: guide ? options.captureContext?.(context) : undefined,
        url: safeUrl,
        heading:
          document.querySelector("h1")?.textContent?.slice(0, 180) ||
          document.title,
      },
      parentOrigin,
    );
  };
  window.addEventListener("message", receive);
  return () => {
    disposed = true;
    enabled = false;
    disposeTarget?.();
    window.removeEventListener("message", receive);
    document.getElementById("player-guidance")?.remove();
  };
}
