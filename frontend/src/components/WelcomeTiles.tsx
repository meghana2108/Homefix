const TILES = [
  { icon: "🖼", title: "Photo", text: "Count things, describe a scene, read an error code.", example: "How many mugs are on the shelf?" },
  { icon: "🔊", title: "Audio", text: "Transcribe a voice note or name a beep or noise.", example: "What is this beeping sound?" },
  { icon: "📄", title: "Document", text: "Answer from a manual with the exact quote and page.", example: "When should I clean the filter?" },
  { icon: "💻", title: "Code", text: "Write a Python function and test it.", example: "Write a function that averages the fridge's watts per hour" },
  { icon: "🎬", title: "Video", text: "Describe a short clip, frame by frame.", example: "Which way is the drum turning?" },
];

export function WelcomeTiles({ onPick }: { onPick: (example: string) => void }) {
  return (
    <section className="welcome">
      <h2>What's wrong at home?</h2>
      <p className="muted">Drop any photo, audio, video, document or CSV.</p>
      <ul className="tiles">
        {TILES.map((t) => (
          <li key={t.title}>
            <button type="button" className="tile" onClick={() => onPick(t.example)}>
              <span className="tile__icon" aria-hidden="true">{t.icon}</span>
              <span className="tile__title">{t.title}</span>
              <span className="tile__text">{t.text}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
