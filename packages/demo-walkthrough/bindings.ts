import { findDemoTarget } from "./targets";
import type { Guide } from "./contracts";
export type TargetRecipe = Guide & {
  selector?: string;
  target?: string;
  text?: string;
  scopeSelector?: string;
  scopeText?: string;
  value?: string;
  literal?: string;
  stay?: boolean;
  provider?: boolean;
  fields?: { selector: string; value: string }[];
};
export function interpolate(
  value: string,
  context: Record<string, string>,
  escape = (s: string) => s,
) {
  return value.replace(/\$([A-Za-z][A-Za-z0-9_]*)/g, (_, key) =>
    escape(context[key] ?? ""),
  );
}
export function resolveTarget(
  doc: Document,
  g: TargetRecipe,
  context: Record<string, string> = {},
) {
  if (g.target) return findDemoTarget(doc, interpolate(g.target, context));
  if (!g.selector) return null;
  const selector = interpolate(g.selector, context, CSS.escape),
    text = g.text ? interpolate(g.text, context) : undefined;
  const matches = [...doc.querySelectorAll<HTMLElement>(selector)].filter(
    (el) =>
      (!text || el.textContent?.includes(text)) &&
      (!g.scopeText ||
        el
          .closest(g.scopeSelector ?? "article")
          ?.textContent?.includes(interpolate(g.scopeText, context))),
  );
  return (
    matches.find((el) => el.getClientRects().length > 0) ?? matches[0] ?? null
  );
}
