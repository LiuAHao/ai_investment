/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#020617',
          2: '#0f172a',
        },
        card: {
          DEFAULT: '#111827',
          2: '#1e293b',
        },
      },
      borderColor: {
        DEFAULT: 'rgba(255, 255, 255, 0.08)',
      },
      animation: {
        'breathe': 'breathe 1.5s ease-in-out infinite',
        'fade-in': 'fadeIn 0.4s ease both',
        'log-slide': 'logSlide 0.3s ease both',
      },
    },
  },
  plugins: [],
};
