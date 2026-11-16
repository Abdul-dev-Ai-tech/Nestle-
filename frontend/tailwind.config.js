/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: '#123E73', 600: '#1B4F8F', 700: '#0E3260', 50: '#EAF1F9' },
        oak: { DEFAULT: '#33271F', 600: '#4A3A2E', 400: '#6B5847' },
        gold: { DEFAULT: '#B8894A', 200: '#E9D9BF' },
        cream: '#F8F6F1',
        line: '#E9E1D4',
        ink: { DEFAULT: '#271F19', 2: '#5A4E44', mute: '#8B7E71' },
        pass: { DEFAULT: '#17804F', bg: '#E3F4EA' },
        fail: { DEFAULT: '#C0342A', bg: '#FBE8E5' },
        warn: { DEFAULT: '#B56A08', bg: '#FCF0D9' },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
        display: ['"Plus Jakarta Sans"', 'Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
      },
      borderRadius: { card: '18px' },
    },
  },
  plugins: [],
};
