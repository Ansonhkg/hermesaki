import type { Capture, Guide, Recording, Step, Workflow } from "./contracts";
import type { ExecutionPlan } from "./runner";
export type RunContext = Record<string, string>;
export type SurfaceDefinition = {
  id: string;
  label: string;
  initialPath: string;
  url: (path: string) => string;
  origins: string[];
};
export type StudioAdapter = {
  id: string;
  workflows: Workflow[];
  actors: { id: string; label: string }[];
  surfaces: SurfaceDefinition[];
  guide: (workflow: string, step: string) => Guide | undefined;
  store: {
    list: () => Promise<Recording[]>;
    save: (run: Recording) => Promise<void>;
  };
  plan: (workflow: Workflow) => ExecutionPlan;
  displayAddress?: (url: string) => string;
  prepareSnapshot: (capture: Capture) => string;
  details?: (context: RunContext) => { label: string; value: string }[];
  navigation?: {
    read: () => { workflow?: string; actor?: string; recording?: string };
    write: (value: {
      workflow: string;
      actor: string;
      recording?: string;
    }) => void;
  };
  preferences?: { read: () => boolean; write: (enabled: boolean) => void };
};
export function browserNavigation() {
  return {
    read: () => Object.fromEntries(new URLSearchParams(location.search)),
    write: (value: Record<string, string | undefined>) => {
      const u = new URL(location.href);
      for (const [k, v] of Object.entries(value)) {
        if (v) u.searchParams.set(k, v);
        else u.searchParams.delete(k);
      }
      history.replaceState(null, "", u);
    },
  };
}
export function browserPreferences(namespace: string) {
  return {
    read: () => localStorage.getItem(namespace + ":subtitles") !== "off",
    write: (enabled: boolean) =>
      localStorage.setItem(namespace + ":subtitles", enabled ? "on" : "off"),
  };
}
