/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#0d1117',
        panel: 'rgba(20, 25, 45, 0.5)',
        border: 'rgba(255, 255, 255, 0.1)',
        accent: '#00D4FF',
        'accent-dim': '#0099FF',
        muted: '#888888',
        cyan: '#00D4FF',
        purple: '#9D4EDD',
      },
    },
  },
  plugins: [],
}
