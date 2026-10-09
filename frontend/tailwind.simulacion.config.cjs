// Tailwind de la simulación (public/simulacion.html). Compila con: npm run build:css
// Usa el mismo sistema de colores que la portada (variables de frontend/public/css/styles.css),
// así las dos páginas cambian juntas entre tema claro y oscuro.
const portada = require('./tailwind.portada.config.cjs');

module.exports = {
  ...portada,
  content: ['./frontend/public/simulacion.html', './frontend/public/js/simulacion.js'],
};
