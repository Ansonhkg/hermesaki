import { createContext, useContext, type ReactNode } from "react";
import type { StudioController } from "./contracts";
const Context = createContext<StudioController | null>(null);
/** The app controller supplies data and actions; the Studio owns presentation. */
export function DemoWalkthroughProvider({
  value,
  children,
}: {
  value: StudioController;
  children: ReactNode;
}) {
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useDemoWalkthrough() {
  const value = useContext(Context);
  if (!value)
    throw Error("DemoWalkthroughStudio requires DemoWalkthroughProvider");
  return value;
}
