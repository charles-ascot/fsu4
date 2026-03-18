/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#0f1117',
        panel: '#161b27',
        border: '#1e2535',
        accent: '#3b82f6',
        'accent-dim': '#1d4ed8',
        muted: '#6b7280',
      },
    },
  },
  plugins: [],
}
