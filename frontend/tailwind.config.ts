import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#05070d",
          900: "#0a0e1a",
          800: "#0f1424",
          700: "#161c30",
          600: "#1f2740",
        },
        neon: {
          blue:   "#3b82f6",
          violet: "#8b5cf6",
          cyan:   "#22d3ee",
          pink:   "#ec4899",
          green:  "#10b981",
          amber:  "#f59e0b",
          red:    "#ef4444",
        },
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"Microsoft YaHei"', "Inter", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "glow": "radial-gradient(circle at 20% 0%, rgba(139,92,246,.18), transparent 50%), radial-gradient(circle at 80% 100%, rgba(59,130,246,.18), transparent 50%)",
      },
      boxShadow: {
        glow: "0 0 40px rgba(59,130,246,.18), inset 0 1px 0 rgba(255,255,255,.04)",
      },
      keyframes: {
        pulse2: {
          "0%, 100%": { opacity: "0.6" },
          "50%":      { opacity: "1" },
        },
        slideUp: {
          "0%":   { transform: "translateY(20px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        shimmer: {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        pulse2: "pulse2 2s ease-in-out infinite",
        slideUp: "slideUp .4s ease-out both",
        shimmer: "shimmer 2s linear infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
