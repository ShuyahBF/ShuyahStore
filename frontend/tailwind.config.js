/** @type {import('tailwindcss').Config} */
import colors from "tailwindcss/colors";

// CHARTE ShuyahStore : bleu nuit (confiance), ocre / orange (chaleur, action principale), vert (signature vérifiée).
// Couleurs sobres, contraste ≥ 4,5:1 (règle 16) ; le bleu nuit #0A1E3D est aussi la police des lignes sélectionnées (règle 3).
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        gray: colors.slate,
        nuit: { DEFAULT: "#0A1E3D", 800: "#12305f", 700: "#1b4384" },
        ocre: { DEFAULT: "#c2410c", clair: "#f6a35b", pale: "#fff4e8" },
        primary: "#1d4ed8",
        "primary-dark": "#1e40af",
        verifie: "#047857",
        ink: "#0f1d3d",
        sable: "#f7f4ee",
      },
      fontFamily: {
        sans: ["Open Sans", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        display: ["Sora", "Open Sans", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      keyframes: {
        "slide-up": { "0%": { transform: "translateY(12px)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
      },
      animation: { "slide-up": "slide-up 0.25s ease-out" },
    },
  },
  plugins: [],
};
