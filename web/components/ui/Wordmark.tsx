import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/cn";

const SIZE = { 20: "text-[20px]", 22: "text-[22px]", 28: "text-[28px]" } as const;
const MARK = { 20: 24, 22: 28, 28: 36 } as const;

/**
 * The Wasila mark (bridge on blue) and "Wasila" in Bricolage 700 (SYSTEM 3.28).
 * Sizes: 20 app bar, 22 marketing nav, 28 sign-in.
 */
export function Wordmark({
  size = 20,
  href,
  className,
}: {
  size?: keyof typeof SIZE;
  href?: string;
  className?: string;
}) {
  const cls = cn(
    "inline-flex items-center gap-8 font-display leading-none font-bold tracking-[-0.02em] text-fg [font-variation-settings:'opsz'_48]",
    SIZE[size],
    className,
  );
  const body = (
    <>
      <Image
        src="/brand/wasila-mark.png"
        alt=""
        aria-hidden
        width={MARK[size]}
        height={MARK[size]}
        priority
        unoptimized
        className="shrink-0 rounded-[22%]"
      />
      <span>Wasila</span>
    </>
  );
  if (href) {
    return (
      <Link href={href} className={cls} aria-label="Wasila home">
        {body}
      </Link>
    );
  }
  return <span className={cls}>{body}</span>;
}
