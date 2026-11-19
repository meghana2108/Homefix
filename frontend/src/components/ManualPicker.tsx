import type { Manual } from "../contract";

export function ManualPicker({ manuals, value, onChange }: {
  manuals: Manual[];
  value: string | null;
  onChange: (id: string | null) => void;
}) {
  if (manuals.length === 0) return null;
  return (
    <fieldset className="manuals">
      <legend>Manuals</legend>
      <label className="manual">
        <input type="radio" name="manual" checked={value === null} onChange={() => onChange(null)} />
        <span>none</span>
      </label>
      {manuals.map((m) => (
        <label key={m.id} className="manual">
          <input type="radio" name="manual" checked={value === m.id} onChange={() => onChange(m.id)} />
          <span>
            {m.title} <span className="muted">· {m.pages} pages</span>
          </span>
        </label>
      ))}
    </fieldset>
  );
}
