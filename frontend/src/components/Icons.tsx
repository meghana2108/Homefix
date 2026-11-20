import {
  AlertTriangle, BookOpenCheck, Camera, CircleAlert, CircleCheck, CircleHelp, CircleX, Code2, Ear, Film, Loader2,
  MessageCircleQuestion, Mic, OctagonAlert, type LucideIcon,
} from "lucide-react";

/** One icon set for the whole app (lucide, one stroke weight). Decorative icons are aria-hidden. */
export const OUTCOME_ICON: Record<string, LucideIcon> = {
  danger: OctagonAlert,
  error: CircleX,
  notfound: CircleHelp,
  cited: BookOpenCheck,
  code: Code2,
  sound: Ear,
  voice: Mic,
  video: Film,
  photo: Camera,
  ask: MessageCircleQuestion,
  working: Loader2,
};

export { AlertTriangle, CircleAlert, CircleCheck };

export function Icon({ as: As, size = 18, className = "" }: { as: LucideIcon; size?: number; className?: string }) {
  return <As aria-hidden="true" focusable="false" size={size} strokeWidth={1.75} className={`icon ${className}`} />;
}
