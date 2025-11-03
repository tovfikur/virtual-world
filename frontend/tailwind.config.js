/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        ocean: '#1e3a8a',
        beach: '#fef3c7',
        plains: '#84cc16',
        forest: '#166534',
        desert: '#fdba74',
        mountain: '#78716c',
        snow: '#f3f4f6',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
