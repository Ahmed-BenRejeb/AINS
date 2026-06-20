"use client";

import { motion, type Variants } from "framer-motion";
import { cn } from "@/lib/utils";

/** Page transition: fade + slight upward movement (y: 10 → 0, opacity: 0 → 1). */
export function PageTransition({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/** Card with a hover lift (y: -2px) and a deepening shadow. */
export function HoverCard({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -2, boxShadow: "0 8px 30px -8px rgba(0,0,0,0.6)" }}
      className={cn("rounded-lg", className)}
    >
      {children}
    </motion.div>
  );
}

/** Container that staggers its direct children's fade-in (0.05s each). */
export const staggerContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

/** A single staggered item (fade + small rise). */
export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] } },
};

export { motion };
