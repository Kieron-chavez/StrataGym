import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          900: "#0D1B2A",
          800: "#112236",
          700: "#162B44",
          600: "#1E3A54",
        },
        accent: {
          blue: "#3B82F6",
          cyan: "#06B6D4",
        },
      },
    },
  },
  plugins: [],
};

export default config;
