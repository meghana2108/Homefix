import { useEffect, useState } from "react";
import { DemoPage } from "./components/demo/DemoPage";
import { Landing } from "./components/landing/Landing";
import { Workspace } from "./components/Workspace";

/** "#/ask" is the workspace, "#/demo" the presenter-paced pitch demo (each with anything under it); everything else is the front door. */
export function routeOf(hash: string): "landing" | "ask" | "demo" {
  if (/^#\/ask(\b|\/|$)/.test(hash)) return "ask";
  return /^#\/demo(\/|$)/.test(hash) ? "demo" : "landing";
}

export default function App() {
  const [route, setRoute] = useState(() => routeOf(window.location.hash));
  useEffect(() => {
    const on = () => {
      setRoute(routeOf(window.location.hash));
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  if (route === "demo") return <DemoPage />;
  return route === "ask" ? <Workspace /> : <Landing />;
}
