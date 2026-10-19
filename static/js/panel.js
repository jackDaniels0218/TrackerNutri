/*
  Gráficos del panel principal.

  Lee los datos que el servidor dejó en <script id="datos-grafico"> (generado
  con el filtro json_script de Django, que escapa el contenido) y los dibuja
  con Chart.js. No calcula nada: todos los números vienen ya calculados del
  backend a partir de los registros reales del usuario.
*/

(function () {
  "use strict";

  // Barra de avance de la meta: se rellena desde el dato del servidor.
  document.querySelectorAll(".barra-relleno").forEach(function (barra) {
    var porcentaje = parseFloat(barra.dataset.porcentaje || "0");
    if (isNaN(porcentaje)) porcentaje = 0;
    barra.style.width = Math.min(porcentaje, 100) + "%";
  });

  var contenedorDatos = document.getElementById("datos-grafico");
  if (!contenedorDatos || typeof Chart === "undefined") {
    return; // Página sin registros o Chart.js no disponible.
  }

  var datos;
  try {
    datos = JSON.parse(contenedorDatos.textContent);
  } catch (error) {
    return;
  }

  var COLORES = ["#2f7d4f", "#c2561f", "#1d4e89"];

  // Gráfico 1: distribución de macronutrientes del día.
  var lienzoMacros = document.getElementById("grafico-macros");
  var hayMacros = datos.macros.valores.some(function (v) { return v > 0; });
  if (lienzoMacros && hayMacros) {
    new Chart(lienzoMacros, {
      type: "doughnut",
      data: {
        labels: datos.macros.etiquetas,
        datasets: [{ data: datos.macros.valores, backgroundColor: COLORES }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: "bottom" },
          tooltip: {
            callbacks: {
              label: function (ctx) { return ctx.label + ": " + ctx.parsed + " g"; }
            }
          }
        }
      }
    });
  }

  // Gráfico 2: calorías de los últimos días frente a la meta.
  var lienzoTendencia = document.getElementById("grafico-tendencia");
  if (lienzoTendencia) {
    var etiquetas = datos.tendencia.etiquetas.map(function (iso) {
      var partes = iso.split("-");
      return partes[2] + "/" + partes[1];
    });
    var meta = datos.tendencia.meta;

    new Chart(lienzoTendencia, {
      type: "bar",
      data: {
        labels: etiquetas,
        datasets: [
          {
            label: "Calorías",
            data: datos.tendencia.valores,
            backgroundColor: COLORES[0]
          },
          {
            label: "Meta",
            type: "line",
            data: datos.tendencia.valores.map(function () { return meta; }),
            borderColor: COLORES[1],
            borderDash: [6, 4],
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        scales: {
          y: { beginAtZero: true, title: { display: true, text: "kcal" } }
        },
        plugins: { legend: { position: "bottom" } }
      }
    });
  }
})();
