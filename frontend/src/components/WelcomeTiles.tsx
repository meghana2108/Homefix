/** First screen: the renter's real problems, one click each. Every capability appears in plain words. */
export interface Scenario {
  icon: string;
  title: string;
  text: string;
  example: string;
  /** When set, picking the scenario also opens the file picker for this kind of file. */
  attach?: "image" | "audio" | "video" | "document";
}

export const SCENARIOS: Scenario[] = [
  { icon: "📷", title: "An error code on the display", text: "Snap the panel. I read the code and look it up in your manual.",
    example: "My washer shows this code. What should I do?", attach: "image" },
  { icon: "🔊", title: "A beep or a strange noise", text: "Record or drop the sound. I tell you what it most likely is.",
    example: "What is this sound?", attach: "audio" },
  { icon: "📖", title: "What does the manual say?", text: "Ask in plain words. I quote the page, or tell you it isn't there.",
    example: "How do I clean the drain filter?" },
  { icon: "⚠️", title: "Burning smell, sparks or gas", text: "I tell you to stop and who to call. I never give repair steps for danger.",
    example: "I smell burning from the outlet behind the fridge" },
  { icon: "🎬", title: "Something moving or leaking", text: "Drop a short clip. I watch it frame by frame.",
    example: "Which way is the water dripping in this clip?", attach: "video" },
  { icon: "⚡", title: "Why is my power bill so high?", text: "Drop a smart-plug CSV. I write the code, test it, then answer.",
    example: "Write a function that finds the hour with the highest watts in my smart-plug CSV" },
];

const PROMISES = [
  { icon: "🔒", text: "Private: runs on this laptop, works with Wi-Fi off" },
  { icon: "📖", text: "Shows the manual page it used, or says it doesn't know" },
  { icon: "⚠️", text: "Stops at danger and tells you who to call" },
];

export function WelcomeTiles({ onPick }: { onPick: (example: string, attach?: Scenario["attach"]) => void }) {
  return (
    <section className="welcome">
      <div className="hero">
        <h2>What's wrong at home?</h2>
        <p className="hero__sub">
          Your first apartment, something's beeping, and the landlord isn't answering. Show me a photo, play me
          the sound, or ask about the manual. I'll tell you what it is and what to do.
        </p>
      </div>
      <ul className="tiles" aria-label="Try one">
        {SCENARIOS.map((t) => (
          <li key={t.title}>
            <button type="button" className="tile" onClick={() => onPick(t.example, t.attach)}>
              <span className="tile__icon" aria-hidden="true">{t.icon}</span>
              <span className="tile__title">{t.title}</span>
              <span className="tile__text">{t.text}</span>
              <span className="tile__try">“{t.example}”</span>
            </button>
          </li>
        ))}
      </ul>
      <ul className="promises">
        {PROMISES.map((p) => (
          <li key={p.text}><span aria-hidden="true">{p.icon}</span> {p.text}</li>
        ))}
      </ul>
    </section>
  );
}
