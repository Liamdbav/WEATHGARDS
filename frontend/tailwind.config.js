/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        wg: {
          bg: "#050818",
          card: "#0D1526",
          border: "#1E3A5F",
          cyan: "#00D4FF",
          violet: "#7B2FBE",
          text: "#E2E8F0",
          muted: "#64748B",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', '"Fira Code"', "monospace"],
      },
      animation: {
        "radar-ping": "radar-ping 1.4s cubic-bezier(0, 0, 0.2, 1) infinite",
        "radar-ping-slow": "radar-ping 1.4s cubic-bezier(0, 0, 0.2, 1) infinite 0.5s",
        "status-pulse": "status-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "glow-cyan": "glow-cyan 3s ease-in-out infinite",
        "shimmer": "shimmer 1.8s ease-in-out infinite",
        "fade-in": "fade-in 0.3s ease-out",
      },
      keyframes: {
        "radar-ping": {
          "0%": { transform: "scale(1)", opacity: "0.6" },
          "100%": { transform: "scale(2.2)", opacity: "0" },
        },
        "status-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.25" },
        },
        "glow-cyan": {
          "0%, 100%": { boxShadow: "0 0 8px rgba(0,212,255,0.15)" },
          "50%": { boxShadow: "0 0 24px rgba(0,212,255,0.35)" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      boxShadow: {
        "cyan-glow": "0 0 20px rgba(0,212,255,0.12)",
        "card-active": "0 0 32px rgba(0,212,255,0.08), inset 0 0 0 1px rgba(0,212,255,0.2)",
      },
      transitionDuration: {
        DEFAULT: "200ms",
      },
    },
  },
  plugins: [],
};
