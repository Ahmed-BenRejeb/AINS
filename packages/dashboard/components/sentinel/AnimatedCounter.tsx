"use client";

import { useEffect, useRef } from "react";
import { animate, useInView } from "framer-motion";

/**
 * Counts a number up to `value` on first view. The final value is the default
 * rendered content (so it is never blank if the observer or JS does not run); the
 * count-up is a pure enhancement that plays when the element scrolls into view.
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
  const final = value.toFixed(decimals) + suffix;

  useEffect(() => {
    if (!inView || !ref.current) return;
    const node = ref.current;
    const controls = animate(0, value, {
      duration: durationSeconds,
      ease: [0.23, 1, 0.32, 1],
      onUpdate: (latest) => {
        node.textContent = latest.toFixed(decimals) + suffix;
      },
      onComplete: () => {
        node.textContent = final;
      },
    });
    return () => controls.stop();
  }, [inView, value, decimals, suffix, durationSeconds, final]);

  // Default content is the real value (robust); the effect re-animates from 0.
  return (
    <span ref={ref} className={className}>
      {final}
    </span>
  );
}
