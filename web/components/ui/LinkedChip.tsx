import { linkedTip } from "@/lib/links";
import type { LinkedInvestorBrief } from "@/lib/api/types";
import { cn } from "@/lib/cn";

import { Tooltip } from "./Tooltip";

/** Two chain links (stroke icon, currentColor), as the linked-cards marker. */
export function LinkIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 16 16"
      className={cn("size-12 shrink-0", className)}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M6.6 9.4a2.6 2.6 0 0 0 3.7 0l2.2-2.2a2.6 2.6 0 0 0-3.7-3.7l-.9.9" />
      <path d="M9.4 6.6a2.6 2.6 0 0 0-3.7 0L3.5 8.8a2.6 2.6 0 0 0 3.7 3.7l.9-.9" />
    </svg>
  );
}

/**
 * Linked cards on a card or row (SPEC §3.10): a quiet outlined chip, link icon and the number
 * of other team members, with their names in the tooltip and the accessible name. A static
 * label (neutral, never cobalt): the team is managed in the investor's file.
 */
export function LinkedChip({
  linked,
  className,
  align = "end",
  side = "bottom",
}: {
  linked: readonly LinkedInvestorBrief[] | null | undefined;
  className?: string;
  align?: "start" | "center" | "end";
  side?: "top" | "bottom";
}) {
  if (!linked || linked.length === 0) return null;
  const tip = linkedTip(linked);
  return (
    <Tooltip tip={tip} align={align} side={side} className={cn("shrink-0", className)}>
      <span
        role="img"
        aria-label={tip}
        className="t-chip inline-flex items-center gap-3 rounded-pill border border-line px-6 font-mono text-[11px] leading-[18px] text-muted tnum"
      >
        <LinkIcon />
        {linked.length}
      </span>
    </Tooltip>
  );
}
