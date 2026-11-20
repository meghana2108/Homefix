import { ScanText } from "lucide-react";
import type { ClarifyEvent, ClarifyOption } from "../contract";
import { Icon } from "./Icons";

/** HomeFix asks instead of guessing: its question, what it could read, and one-click replies. */
export function ClarifyCard({ clarify, onReply, canReply }: {
  clarify: ClarifyEvent; onReply?: (o: ClarifyOption) => void; canReply: boolean;
}) {
  return (
    <section className="clarify" aria-label="HomeFix's question for you">
      <p className="clarify__q">{clarify.question}</p>
      {clarify.seen && (
        <figure className="evidence">
          <p className="evidence__label"><Icon as={ScanText} size={16} />What HomeFix could read</p>
          <div className="card card--seen"><blockquote className="seen">{clarify.seen}</blockquote></div>
        </figure>
      )}
      {clarify.options.length > 0 && (
        <div className="clarify__opts" role="group" aria-label="Reply with one click">
          {clarify.options.map((o) => (
            <button key={`${o.label}-${o.manual_id ?? ""}`} type="button" className="btn btn--small clarify__opt"
              disabled={!canReply || !onReply} onClick={(e) => { e.stopPropagation(); onReply?.(o); }}>
              {o.label}
            </button>
          ))}
        </div>
      )}
      {canReply && <p className="clarify__hint">Or type your answer below. Your files go with it.</p>}
    </section>
  );
}
