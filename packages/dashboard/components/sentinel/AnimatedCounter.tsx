"use client";

import { useEffect, useRef } from "react";
import { animate, useInView } from "framer-motion";

/**
 * Counts a number up from 0 to `value` on first view. Supports a suffix ("%") and
 * fixed decimals; renders as tabular-nums monospace so it doesn't jitter.
 */
export function AnimatedCounter({
  value,
  decimals = 0,
  suffix = "",
  durationSeconds = 1.1,
  className,
}: {
  value: number;
  decimals?: number;
  suffix?: string;
  durationSeconds?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-20px" });

  useEffect(() => {
    if (!inView || !ref.current) return;
    const node = ref.current;
    const controls = animate(0, value, {
      duration: durationSeconds,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (latest) => {
        node.textContent = latest.toFixed(decimals) + suffix;
      },
    });
    return () => controls.stop();
  }, [inView, value, decimals, suffix, durationSeconds]);

  return (
    <span ref={ref} className={className}>
      {(0).toFixed(decimals) + suffix}
    </span>
  );
}
