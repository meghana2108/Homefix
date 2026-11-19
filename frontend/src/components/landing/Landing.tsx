import {
  BookOpenCheck, Camera, Code2, FileText, Film, Lock, Mic, OctagonAlert, ShieldCheck, Volume2, WifiOff,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Icon } from "../Icons";
import { Stamp } from "../Stamp";
import { Wordmark } from "../Wordmark";
import { HeroDemo } from "./HeroDemo";

export const ASK_HREF = "#/ask";

function Section({ id, title, intro, children }: { id: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section className="section" aria-labelledby={`${id}-h`} id={id}>
      <div className="section__inner">
        <div>
          <h2 id={`${id}-h`}>{title}</h2>
          {intro && <p className="section__intro">{intro}</p>}
        </div>
        <div style={{ minWidth: 0 }}>{children}</div>
      </div>
    </section>
  );
}

function Bar() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 8);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <div className={`bar ${scrolled ? "bar--scrolled" : ""}`}>
      <div className="bar__inner">
        <Wordmark />
        <a className="btn btn--small" href={ASK_HREF}>Open HomeFix</a>
      </div>
    </div>
  );
}

const POINTS = [
  { icon: Camera, title: "It reads the display", text: "Photograph the panel. HomeFix reads the error code and looks it up in your manual." },
  { icon: BookOpenCheck, title: "It shows you the page", text: "Every answer from a manual comes with the exact words and the page. If the manual doesn't say, it tells you so instead of guessing." },
  { icon: OctagonAlert, title: "It stops at danger", text: "Gas, burning, sparks or water near power get one clear message: stop, get safe, and who to call. Never repair steps." },
  { icon: WifiOff, title: "It works offline", text: "Every model runs on this laptop. Photos of your home never leave it, and it still works when the Wi-Fi is what's broken." },
];

const INPUTS = [
  { icon: Camera, name: "A photo", text: "An error code, a leak, a breaker panel. Count things or read a label." },
  { icon: Volume2, name: "A sound", text: "A beep, a chirp, a rattle. It names the closest matching household sounds." },
  { icon: Mic, name: "A voice note", text: "Speak your question, or drop a voicemail from the landlord. It writes out the words." },
  { icon: FileText, name: "A document", text: "A manual, a lease, a house guide. Answers come with the quote and page." },
  { icon: Film, name: "A short video", text: "Something dripping, spinning or blinking. It watches the clip frame by frame." },
  { icon: Code2, name: "A spreadsheet", text: "A smart-plug CSV. It writes a small program, tests it, then answers." },
];

const EXAMPLES = [
  { q: "A photo of the washer showing E21, “What should I do?”",
    outcome: { kind: "answered", label: "From the manual, page 2", icon: "cited" } as const,
    a: "E21 means the washer cannot drain. Turn it off, clean the drain pump filter, check the hose. If it comes back, call maintenance." },
  { q: "“Is there a warranty on the washer?”",
    outcome: { kind: "notfound", label: "Not in the document", icon: "notfound" } as const,
    a: "The guide doesn't cover a warranty, so HomeFix says so. It doesn't invent an answer." },
  { q: "“I smell burning from the outlet behind the fridge”",
    outcome: { kind: "danger", label: "Stop: this could be dangerous", icon: "danger" } as const,
    a: "Stop using it, switch off the breaker if it's safe, and if there's smoke, leave and call 911. No repair steps." },
];

const LIMITS = [
  { lead: "It answers only from what you give it.", text: "A photo, a sound, a manual or a file. Ask about the washer with no manual loaded and it will ask for one." },
  { lead: "It is not a repair person.", text: "It tells you what a code means and what the manual says to do. Anything inside the machine is a job for maintenance." },
  { lead: "It can misread or miscount.", text: "The models are small enough to run on a laptop. The 8 GB MacBook Air gets about 3 in 4 practice questions right." },
  { lead: "Real manuals print error codes as pictures.", text: "So a code can only be matched when it is typed out, as in a landlord's guide. Our Unit 4B guide is a sample we wrote." },
  { lead: "A video's sound is not checked.", text: "It watches the frames of a clip, not its audio track." },
  { lead: "It is a hackathon prototype.", text: "Not professional or safety advice. In an emergency, call 911." },
];

/** The front door: what HomeFix is for, one worked example, what you can bring, what an answer looks like,
 *  and what it can't do. "Ask about something at home" opens the workspace (#/ask). */
export function Landing() {
  return (
    <div className="landing">
      <a className="skip" href="#top">Skip to content</a>
      <Bar />
      <main id="top">
        <header className="hero">
          <div className="hero__glow" aria-hidden="true" />
          <div className="hero__inner">
            <div style={{ minWidth: 0 }}>
              <h1>Is it broken, or is it normal?</h1>
              <p className="hero__lead">
                Your first apartment, the washer is beeping, and the landlord isn't answering. Show HomeFix a photo,
                play it the sound, or ask about the manual. It tells you what's going on and what to do, and shows
                you where it found the answer.
              </p>
              <div className="hero__actions">
                <a className="btn btn--primary btn--big" href={ASK_HREF}>
                  Ask about something at home
                </a>
                <a className="textlink" href="#example">See what an answer looks like</a>
              </div>
              <ul className="hero__facts">
                <li><Icon as={Lock} size={18} />Runs on this laptop. Nothing you send leaves it.</li>
                <li><Icon as={BookOpenCheck} size={18} />Quotes the manual's page, or says the manual doesn't say.</li>
                <li><Icon as={ShieldCheck} size={18} />Checks every question for danger first.</li>
              </ul>
            </div>
            <HeroDemo />
          </div>
        </header>

        <Section id="why" title="Why HomeFix?">
          <div className="prose">
            <p>
              Most things that go wrong in a first apartment are small: a code on the washer, a tripped breaker, a smoke
              alarm that chirps. The answer is usually in a manual nobody has read, and the landlord takes a day to reply.
            </p>
            <p>
              A general chatbot will answer anyway, and a confident wrong answer about a gas smell is worse than none.
              HomeFix only answers from what you give it, shows the words it used, and stops when something sounds dangerous.
            </p>
            <p><strong>And it does all of it on your own laptop, with the Wi-Fi off.</strong></p>
          </div>
        </Section>

        <Section id="what" title="What you get">
          <ul className="points">
            {POINTS.map((p) => (
              <li key={p.title} className="point">
                <span className="point__icon" aria-hidden="true"><Icon as={p.icon} size={20} /></span>
                <h3>{p.title}</h3>
                <p>{p.text}</p>
              </li>
            ))}
          </ul>
        </Section>

        <Section id="bring" title="Bring whatever you have" intro="Drop it in, or attach it, and ask in your own words.">
          <ul className="inputs">
            {INPUTS.map((i) => (
              <li key={i.name}><Icon as={i.icon} size={20} /><strong>{i.name}</strong><span>{i.text}</span></li>
            ))}
          </ul>
        </Section>

        <Section id="example" title="What an answer looks like" intro="Every answer starts with a stamp, so you know at a glance what kind of answer it is.">
          <figure style={{ margin: 0 }}>
            <ol className="examples" aria-label="Three example answers">
              {EXAMPLES.map((e) => (
                <li key={e.q}>
                  <div><Stamp outcome={e.outcome} size="sm" /></div>
                  <div>
                    <p className="examples__q">{e.q}</p>
                    <p className="examples__a">{e.a}</p>
                  </div>
                </li>
              ))}
            </ol>
            <figcaption className="caption">Real answers from the 8 GB MacBook Air, using the sample Unit 4B guide.</figcaption>
          </figure>
        </Section>

        <Section id="limits" title="What HomeFix can't do">
          <ul className="limits">
            {LIMITS.map((l) => <li key={l.lead}><strong>{l.lead}</strong> <span>{l.text}</span></li>)}
          </ul>
        </Section>

        <section className="cta" aria-labelledby="cta-h">
          <div className="cta__inner">
            <div className="cta__panel">
              <h2 id="cta-h">Something beeping right now?</h2>
              <p>Take a photo of the display, or record the sound, and ask. You'll see each step as HomeFix works.</p>
              <a className="btn btn--big" href={ASK_HREF}>Ask about something at home</a>
            </div>
          </div>
        </section>
      </main>
      <footer className="footer">Built by Meghana and Akshayaa for the IEEE AI Hackathon 2026. Runs with Ollama on Apple Silicon, offline.</footer>
    </div>
  );
}
