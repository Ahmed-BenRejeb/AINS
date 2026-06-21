import type { Config } from "tailwindcss";

/**
 * Sentinel "mission-control" dark theme.
 *
 * One signal accent (emerald) on a near-black canvas. The three verdict colors
 * (emerald / red / amber) are reserved for real pass/fail/uncertain state, never
 * decoration. Radii cap at 16px on surfaces (impeccable). Easing curves are the
 * strong ease-out / drawer curves from the emil-design-eng skill.
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Neutral ramp: near-black tinted toward the emerald hue (instrument green-black).
        canvas: "#06090A",
        "canvas-2": "#0A0F10",
        surface: "#0E1413",
        "surface-2": "#131B19",
        hairline: "#1C2522",
        "hairline-strong": "#27332F",
        background: "#070809",
        foreground: "#E8EDEC",
        muted: {
          DEFAULT: "#131B19",
          foreground: "#8A9A94",
        },
        // Back-compat aliases (older components use these names) mapped to the new
        // palette so the inner screens inherit the refreshed surfaces.
        card: "#0E1413",
        "card-hover": "#131B19",
        border: "#1C2522",
        // Single brand accent.
        accent: {
          DEFAULT: "#34E5B0", // emerald-mint signal
          soft: "#1FB890",
          ink: "#052b22",
        },
        verdict: {
          pass: "#34E5B0",
          fail: "#FB5E6D",
          uncertain: "#F5B445",
        },
      },
      fontFamily: {
        // Distinctive display grotesque (Bricolage) — deliberately not Geist for
        // headlines, to escape the Vercel-clone reflex. Geist Sans for body, Geist
        // Mono for telemetry (ids / scores), which the instrument register earns.
        display: ['"Bricolage Grotesque Variable"', "var(--font-geist-sans)", "sans-serif"],
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        xl: "1rem", // 16px cap for surfaces
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.375rem",
      },
      transitionTimingFunction: {
        // emil-design-eng strong curves
        out: "cubic-bezier(0.23, 1, 0.32, 1)",
        "in-out": "cubic-bezier(0.77, 0, 0.175, 1)",
        drawer: "cubic-bezier(0.32, 0.72, 0, 1)",
      },
      boxShadow: {
        // No "ghost-card" (1px border + wide soft shadow). Defined, tight elevation.
        elevated: "0 12px 40px -16px rgba(0,0,0,0.7)",
        "accent-glow": "0 0 0 1px rgba(52,229,176,0.18), 0 16px 50px -20px rgba(52,229,176,0.28)",
        // Back-compat aliases used by older components.
        card: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 1px 3px 0 rgba(0,0,0,0.4)",
        lift: "0 12px 40px -16px rgba(0,0,0,0.7)",
      },
      keyframes: {
        "aurora-drift": {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1)", opacity: "0.55" },
          "50%": { transform: "translate3d(2%,-3%,0) scale(1.08)", opacity: "0.8" },
        },
        shimmer: { "100%": { transform: "translateX(100%)" } },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(52,229,176,0.45)" },
          "70%": { boxShadow: "0 0 0 8px rgba(52,229,176,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(52,229,176,0)" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        aurora: "aurora-drift 14s ease-in-out infinite",
        shimmer: "shimmer 1.5s infinite",
        "pulse-ring": "pulse-ring 2.4s ease-out infinite",
        "fade-up": "fade-up 0.5s cubic-bezier(0.23,1,0.32,1) both",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
