import type { ReactNode } from "react";

/** **bold** spans inside one line. Everything else is plain text (never HTML). */
function inline(line: string, key: string): ReactNode[] {
  const parts = line.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**") && p.length > 4
      ? <strong key={`${key}-${i}`}>{p.slice(2, -2)}</strong>
      : p,
  );
}

const NUMBERED = /^\s*(\d+)[.)]\s+(.*)$/;
const BULLET = /^\s*[-*•]\s+(.*)$/;

type Block = { kind: "p"; lines: string[] } | { kind: "ol" | "ul"; items: string[] };

/** Split model text into paragraphs and lists. A list needs 2+ items in a row, so a count answer
 *  such as "4. Four mugs." stays a sentence. */
export function blocks(text: string): Block[] {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const out: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    let list = false;
    for (const [re, kind] of [[NUMBERED, "ol"], [BULLET, "ul"]] as const) {
      let j = i;
      const items: string[] = [];
      while (j < lines.length && re.test(lines[j])) {
        const m = lines[j].match(re)!;
        items.push(kind === "ol" ? m[2] : m[1]);
        j++;
      }
      if (items.length >= 2) {
        out.push({ kind, items });
        i = j;
        list = true;
        break;
      }
    }
    if (list) continue;
    const prev = out[out.length - 1];
    if (prev?.kind === "p" && i > 0 && lines[i - 1].trim()) prev.lines.push(line);
    else out.push({ kind: "p", lines: [line] });
    i++;
  }
  return out;
}

export function AnswerText({ text, streaming }: { text: string; streaming?: boolean }) {
  const bs = blocks(text);
  return (
    <div className="answer">
      {bs.map((b, bi) => {
        const last = bi === bs.length - 1;
        const cursor = streaming && last ? <span className="cursor" aria-hidden="true">▍</span> : null;
        if (b.kind === "p") {
          return (
            <p key={bi}>
              {b.lines.flatMap((l, li) => [...(li ? [<br key={`br${li}`} />] : []), ...inline(l, `${bi}-${li}`)])}
              {cursor}
            </p>
          );
        }
        const Tag = b.kind;
        return (
          <Tag key={bi}>
            {b.items.map((it, ii) => <li key={ii}>{inline(it, `${bi}-${ii}`)}{ii === b.items.length - 1 && cursor}</li>)}
          </Tag>
        );
      })}
    </div>
  );
}
