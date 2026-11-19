/** The HomeFix mark: a house with a wrench, same drawing as the app icon. */
export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <rect width="100" height="100" rx="24" fill="var(--pen)" />
      <path d="M17 47 L50 18 L83 47" fill="none" stroke="#fff" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="26" y="44" width="48" height="38" rx="3" fill="none" stroke="#fff" strokeWidth="8" />
      <path d="M41 74 L55 60" stroke="#fff" strokeWidth="6" strokeLinecap="round" />
      <circle cx="57" cy="58" r="8" fill="#fff" />
      <circle cx="61" cy="53" r="4" fill="var(--pen)" />
    </svg>
  );
}
