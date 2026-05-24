import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: 'hsl(0 0% 100%)',
        fg: 'hsl(222 47% 11%)',
        muted: 'hsl(210 16% 93%)',
        'muted-fg': 'hsl(215 16% 47%)',
        border: 'hsl(214 32% 91%)',
        accent: 'hsl(221 83% 53%)',
        'accent-fg': 'hsl(0 0% 100%)',
        danger: 'hsl(0 84% 60%)',
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
