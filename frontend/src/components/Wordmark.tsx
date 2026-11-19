import { Logo } from "./Logo";

export function Wordmark({ href = "#/", tagline = true }: { href?: string; tagline?: boolean }) {
  return (
    <a className="wordmark" href={href} aria-label="HomeFix home">
      <Logo size={32} />
      <span>
        <span className="wordmark__name">HomeFix</span>
        {tagline && <span className="wordmark__tag">Help for your first apartment</span>}
      </span>
    </a>
  );
}
