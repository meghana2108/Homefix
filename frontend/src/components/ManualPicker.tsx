import type { Manual } from "../contract";

/** "auto": the backend uses a manual when the question is about an appliance (app/orchestrate.py). */
export const AUTO = "auto";

export function ManualPicker({ manuals, value, onChange }: {
  manuals: Manual[];
  value: string | null;
  onChange: (id: string | null) => void;
}) {
  if (manuals.length === 0) return null;
  return (
    <label className="manualpick">
      <span aria-hidden="true">📘</span>
      <span className="visually-hidden">Manual</span>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value || null)} aria-label="Manual">
        <option value={AUTO}>Manual: automatic</option>
        {manuals.map((m) => (
          <option key={m.id} value={m.id}>{m.title} · {m.pages} pages</option>
        ))}
        <option value="">No manual</option>
      </select>
    </label>
  );
}
