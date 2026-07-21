import type { Config } from "tailwindcss";

// PlacementOS design tokens — locked per the Phase 2 design plan.
// Every color and type choice here is deliberate, not a framework
// default — see docs/PlacementOS_Design_System.md for the reasoning
// behind each choice, and Decision Log #006 for the boundary this
// system respects (presentation-layer only, engine untouched).
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#1C2B33", // primary text/headers — calm authority, warmer than pure black
          light: "#3D4C54",
        },
        paper: {
          DEFAULT: "#F7F5F0", // page background — warm, clean, deliberately NOT the AI-cliché cream (#F4F1EA)
          card: "#FFFFFF",
        },
        evidence: {
          DEFAULT: "#C08B2C", // the signature accent — used ONLY to mark real quoted evidence, never decoratively
          light: "#FAEEDA",
          dark: "#854F0B",
        },
        sage: {
          DEFAULT: "#5F7A68", // calm secondary/success tone
          light: "#E8EEE9",
          dark: "#3B4F42",
        },
        clay: {
          DEFAULT: "#A54F42", // muted warning/contradiction tone — deliberately not alarming
          light: "#F5E8E6",
        },
      },
      fontFamily: {
        // Display/headline face — editorial, restrained, used for
        // headings only. Never body text (per skill guidance: don't
        // let the display face become a neutral delivery vehicle).
        display: ["var(--font-fraunces)", "Georgia", "serif"],
        // Body/UI face — clean, readable, deliberately not the
        // overused Inter default.
        sans: ["var(--font-source-sans)", "Arial", "sans-serif"],
        // Reserved exclusively for quoted evidence excerpts in the
        // feedback report — visually distinguishes "this is a real
        // quote" from surrounding AI commentary. Do not use for
        // anything else; using it elsewhere dilutes the signal.
        evidence: ["var(--font-plex-mono)", "Courier New", "monospace"],
      },
      borderRadius: {
        card: "12px",
      },
    },
  },
  plugins: [],
};
export default config;
