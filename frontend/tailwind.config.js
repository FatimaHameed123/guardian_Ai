/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: { DEFAULT: "#0f1419", light: "#f8fafc" },
        panel: { DEFAULT: "#161b22", light: "#ffffff" },
        border: { DEFAULT: "#30363d", light: "#e2e8f0" },
        accent: "#3b82f6",
      },
    },
  },
  plugins: [],
};
