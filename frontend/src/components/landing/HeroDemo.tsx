import { Check, Circle, Loader2, Pause, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { Icon } from "../Icons";
import { Stamp } from "../Stamp";
import { SevenSeg } from "./SevenSeg";

/** The worked example on the front door, one step at a time on a loop. Real wording from a real run
 *  (E21 photo + the sample Unit 4B guide, 9.4 s on the 8 GB MacBook Air). */
export const DEMO_STEPS = [
  "Checked for danger: nothing found",
  "Read E21 from the display",
  "Using the manual: Unit 4B apartment guide",
  "Found word for word on page 2",
];
const LAST = DEMO_STEPS.length; // stage LAST = the answer is shown
const BEAT_MS = 1300;

function reducedMotion(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function HeroDemo() {
  const calm = reducedMotion();
  const [stage, setStage] = useState(calm ? LAST : 0);
  const [playing, setPlaying] = useState(!calm);

  useEffect(() => {
    if (!playing) return;
    const id = window.setTimeout(() => setStage((s) => (s >= LAST + 2 ? 0 : s + 1)), stage >= LAST ? BEAT_MS * 2 : BEAT_MS);
    return () => window.clearTimeout(id);
  }, [stage, playing]);

  const shown = Math.min(stage, LAST);
  return (
    <figure className="demo" aria-label="An example: a photo of a washer display, answered from the manual" style={{ margin: 0 }}>
      <div className="demo__photo">
        <SevenSeg text="E21" label="A washer display showing E21" />
        <p>The photo: your washer's display</p>
      </div>
      <div className="demo__body">
        <p className="demo__q">“My washer shows this code. What should I do?”</p>
        <ol className="demo__steps" aria-label="What HomeFix does">
          {DEMO_STEPS.map((text, i) => {
            const state = i < shown ? "done" : i === shown && shown < LAST ? "now" : "todo";
            const As = state === "done" ? Check : state === "now" ? Loader2 : Circle;
            return (
              <li key={text} className={`demo__step demo__step--${state}`}>
                <Icon as={As} size={16} className={state === "now" ? "spin" : ""} />
                {text}
              </li>
            );
          })}
        </ol>
        <div className={`demo__answer ${shown >= LAST ? "demo__answer--on" : ""}`} aria-hidden={shown < LAST}>
          <Stamp outcome={{ kind: "answered", label: "From the manual, page 2", icon: "cited" }} size="sm" />
          <p style={{ margin: "0.6rem 0 0" }}>
            <span className="mark">E21 means the washer cannot drain.</span> Turn it off and unplug it, clean the drain pump
            filter behind the small door at the bottom right, and check the hose for kinks.
          </p>
        </div>
      </div>
      <div className="demo__controls">
        <span>{shown >= LAST ? "Answered in 9.4 s, on an 8 GB laptop" : `Step ${shown + 1} of ${LAST}`}</span>
        <button type="button" className="btn btn--quiet btn--small" onClick={() => setPlaying((p) => !p)}
          aria-label={playing ? "Pause the example" : "Play the example"}>
          <Icon as={playing ? Pause : Play} size={16} />{playing ? "Pause" : "Play"}
        </button>
      </div>
    </figure>
  );
}
