// Tailwind de la portada (public/index.html). Compila con: npm run build:css
// Sistema visual: estilo "Accesible y ético" (ui-ux-pro-max) con la estructura sobria de la
// guía Apple (design-md). Los colores vienen de variables CSS (public/css/styles.css) para el modo oscuro.
const v = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

module.exports = {
  content: ['./public/index.html', './public/js/landing.js'],
  darkMode: 'media',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Figtree', 'system-ui', 'sans-serif'],
      },
      colors: {
        surface: v('surface'),
        // Único color de acción: botones, enlaces, foco, burbuja del médico, micrófono.
        brand: {
          50: v('brand-50'),
          100: v('brand-100'),
          500: v('brand-500'),
          600: v('brand-600'),
          700: v('brand-700'),
          900: v('brand-900'),
        },
        // Alias del mismo color para las acciones principales.
        accent: {
          50: v('brand-50'),
          100: v('brand-100'),
          600: v('brand-600'),
          700: v('brand-700'),
        },
        // Neutros fríos con un leve tinte verde azulado; se invierten en modo oscuro.
        slate: {
          50: v('slate-50'),
          100: v('slate-100'),
          200: v('slate-200'),
          300: v('slate-300'),
          400: v('slate-400'),
          500: v('slate-500'),
          600: v('slate-600'),
          700: v('slate-700'),
          800: v('slate-800'),
          900: v('slate-900'),
          950: v('slate-950'),
        },
      },
      borderRadius: {
        card: '18px',
      },
      boxShadow: {
        xs: '0 1px 2px 0 rgb(16 38 43 / 0.05)',
        // Única sombra del sistema: para la ilustración y lo que flota sobre ella.
        float: '3px 5px 30px 0 rgb(16 38 43 / 0.18)',
      },
    },
  },
  plugins: [require('@tailwindcss/forms'), require('@tailwindcss/container-queries')],
};
