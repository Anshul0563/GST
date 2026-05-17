import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "#1746A2",
          foreground: "#ffffff"
        },
        accent: {
          DEFAULT: "#F58220",
          foreground: "#111827"
        },
        saffron: "#F58220",
        navy: "#10244d",
        success: "#0F9F6E",
        muted: {
          DEFAULT: "#F4F7FB",
          foreground: "#64748B"
        }
      },
      boxShadow: {
        soft: "0 18px 50px rgba(23, 70, 162, 0.10)"
      }
    }
  },
  plugins: [require("tailwindcss-animate")]
};

export default config;
