import { useEffect, useState } from "react";
import { Landing } from "./components/landing/Landing";
import { Workspace } from "./components/Workspace";

/** "#/ask" (or anything under it) is the workspace; everything else is the front door. */
export function routeOf(hash: string): "landing" | "ask" {
  return /^#\/ask(\b|\/|$)/.test(hash) ? "ask" : "landing";
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
  return route === "ask" ? <Workspace /> : <Landing />;
}
