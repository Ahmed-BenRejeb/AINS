import type { Config } from "tailwindcss";

/**
 * Sentinel dark theme. The palette is intentionally narrow: a near-black canvas
 * (#0A0A0A), slightly lifted cards (#141414), hairline borders (#1F1F1F), and the
 * three verdict accents (emerald / red / amber). Everything else is a neutral grey.
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
        canvas: "#0A0A0A",
        card: "#141414",
        "card-hover": "#181818",
        hairline: "#1F1F1F",
        border: "#1F1F1F",
        background: "#0A0A0A",
        foreground: "#EDEDED",
        muted: {
          DEFAULT: "#161616",
          foreground: "#8A8A8A",
        },
        verdict: {
          pass: "#10b981", // emerald-500
          fail: "#ef4444", // red-500
          uncertain: "#f59e0b", // amber-500
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: [
          "var(--font-mono)",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      borderRadius: {
        lg: "0.75rem",
        md: "0.5rem",
        sm: "0.375rem",
      },
      boxShadow: {
        card: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 1px 3px 0 rgba(0,0,0,0.4)",
        lift: "0 8px 30px -8px rgba(0,0,0,0.6)",
      },
      keyframes: {
        "verdict-pulse": {
          "0%": { boxShadow: "0 0 0 0 rgba(16,185,129,0.35)" },
          "70%": { boxShadow: "0 0 0 10px rgba(16,185,129,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(16,185,129,0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "verdict-pulse": "verdict-pulse 1.6s ease-out 1",
        shimmer: "shimmer 1.5s infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
