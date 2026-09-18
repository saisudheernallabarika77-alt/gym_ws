import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Fitora brand — warm energetic orange against a deep charcoal
        brand: {
          50:  "#FFF3EF", 100: "#FFE2D8", 200: "#FFC3AE", 300: "#FF9D7C",
          400: "#FF7550", 500: "#FF4D2E", 600: "#ED3311", 700: "#C4230A",
          800: "#9C1F0E", 900: "#7E1E11",
        },
        ink: {
          50:  "#F6F7F9", 100: "#ECEEF2", 200: "#D5D9E0", 300: "#B0B7C3",
          400: "#848E9E", 500: "#657084", 600: "#50596B", 700: "#424957",
          800: "#23262d", 850: "#1a1d23", 900: "#16181d", 950: "#0f1115",
        },
        success: "#22C55E",
        warning: "#F59E0B",
        danger:  "#EF4444",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "system-ui", "sans-serif"],
      },
      borderRadius: { "4xl": "2rem" },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #FF4D2E 0%, #FF8A3D 100%)",
        "dark-mesh":
          "radial-gradient(at 20% 0%, rgba(255,77,46,0.12) 0px, transparent 50%)," +
          "radial-gradient(at 80% 20%, rgba(255,138,61,0.08) 0px, transparent 50%)," +
          "radial-gradient(at 40% 90%, rgba(255,77,46,0.06) 0px, transparent 50%)",
      },
      keyframes: {
        "fade-up": {
          "0%":   { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in": {
          "0%":   { opacity: "0", transform: "translateX(-10px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        shimmer: {
          "0%":   { backgroundPosition: "-500px 0" },
          "100%": { backgroundPosition: "500px 0" },
        },
        "pulse-ring": {
          "0%":   { transform: "scale(0.9)", opacity: "0.7" },
          "70%":  { transform: "scale(1.25)", opacity: "0" },
          "100%": { transform: "scale(1.25)", opacity: "0" },
        },
        float: {
          "0%,100%": { transform: "translateY(0)" },
          "50%":     { transform: "translateY(-6px)" },
        },
      },
      animation: {
        "fade-up":   "fade-up .45s cubic-bezier(.16,1,.3,1) both",
        "slide-in":  "slide-in .35s cubic-bezier(.16,1,.3,1) both",
        shimmer:     "shimmer 1.6s linear infinite",
        "pulse-ring":"pulse-ring 2s cubic-bezier(.24,0,.38,1) infinite",
        float:       "float 4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
