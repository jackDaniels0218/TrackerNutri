/*
  Gráficos de NutriRegional (RF18) con Chart.js.

  No calcula nada: dibuja las series que el servidor ya preparó a partir de
  los registros reales (core/services/reportes.py). Si el usuario eligió
  ocultar las cifras, los ejes y las etiquetas no muestran números: solo la
  forma de la tendencia.
*/
window.NutriGraficos = (function () {
  "use strict";

  var C = { verde: "#2f7d4f", verdeSuave: "rgba(47,125,79,.15)", naranja: "#b4501c", azul: "#1d4e89", morado: "#7a52b3", gris: "#8a94a3" };

  function base(ocultar, extra) {
    var opciones = {
      responsive: true, maintainAspectRatio: false, spanGaps: true,
      plugins: { legend: { position: "bottom" }, tooltip: { enabled: !ocultar } },
      scales: { y: { beginAtZero: true, ticks: { display: !ocultar } } }
    };
    return Object.assign(opciones, extra || {});
  }

  function crear(id, config) {
    var lienzo = document.getElementById(id);
    if (!lienzo || typeof Chart === "undefined") return null;
    return new Chart(lienzo, config);
  }

  // Ingesta diaria frente a la meta, con media móvil de 7 días y rango.
  function ingesta(id, s, ocultar) {
    return crear(id, {
      type: "line",
      data: {
        labels: s.etiquetas,
        datasets: [
          { label: "Rango máximo", data: s.ingesta.max, borderWidth: 0, pointRadius: 0, backgroundColor: C.verdeSuave, fill: "+1" },
          { label: "Rango mínimo", data: s.ingesta.min, borderWidth: 0, pointRadius: 0, fill: false },
          { label: "Energía estimada", data: s.ingesta.kcal, borderColor: C.verde, backgroundColor: C.verde, tension: .25 },
          { label: "Media móvil 7 días", data: s.ingesta.media_movil, borderColor: C.azul, borderDash: [4, 3], pointRadius: 0 },
          { label: "Meta", data: s.ingesta.meta, borderColor: C.naranja, borderDash: [6, 4], pointRadius: 0, stepped: true }
        ]
      },
      options: base(ocultar, {
        plugins: { legend: { position: "bottom", labels: { filter: function (i) { return i.text.indexOf("Rango") !== 0; } } }, tooltip: { enabled: !ocultar } }
      })
    });
  }

  function peso(id, s, ocultar) {
    return crear(id, {
      type: "line",
      data: {
        labels: s.etiquetas,
        datasets: [
          { label: "Peso registrado", data: s.peso.real, borderColor: C.gris, backgroundColor: C.gris, showLine: false },
          { label: "Peso tendencial (media móvil)", data: s.peso.tendencial, borderColor: C.verde, tension: .3, pointRadius: 0 }
        ]
      },
      options: base(ocultar, { scales: { y: { beginAtZero: false, ticks: { display: !ocultar } } } })
    });
  }

  function macros(id, s, ocultar) {
    return crear(id, {
      type: "bar",
      data: {
        labels: s.etiquetas,
        datasets: [
          { label: "Proteínas (g)", data: s.macros.proteinas, backgroundColor: C.verde },
          { label: "Carbohidratos (g)", data: s.macros.carbohidratos, backgroundColor: C.azul },
          { label: "Grasas (g)", data: s.macros.grasas, backgroundColor: C.naranja }
        ]
      },
      options: base(ocultar, { scales: { x: { stacked: true }, y: { stacked: true, ticks: { display: !ocultar } } } })
    });
  }

  function barras(id, etiquetas, datos, etiqueta, color, ocultar) {
    return crear(id, {
      type: "bar",
      data: { labels: etiquetas, datasets: [{ label: etiqueta, data: datos, backgroundColor: color }] },
      options: base(ocultar)
    });
  }

  function evolucionMeta(id, lista, ocultar) {
    return crear(id, {
      type: "line",
      data: {
        labels: lista.map(function (m) { return m.fecha; }),
        datasets: [{ label: "Meta diaria (kcal)", data: lista.map(function (m) { return m.kcal; }), borderColor: C.naranja, stepped: true }]
      },
      options: base(ocultar, { scales: { y: { beginAtZero: false, ticks: { display: !ocultar } } } })
    });
  }

  return { ingesta: ingesta, peso: peso, macros: macros, barras: barras, evolucionMeta: evolucionMeta, colores: C };
})();
