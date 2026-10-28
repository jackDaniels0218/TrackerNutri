/*
  Ayudas de formulario. Todo funciona igual sin JavaScript; esto solo mejora
  la experiencia:
  1. Contador de caracteres y estado «Interpretando…» del texto libre.
  2. Botón «Otro alimento» del registro manual: clona la última fila del
     formset de Django y actualiza sus índices.
*/
(function () {
  "use strict";

  var formulario = document.getElementById("formulario-analisis");
  if (formulario) {
    var texto = formulario.querySelector("textarea");
    var contador = document.getElementById("contador");
    var actualizar = function () {
      if (contador && texto) contador.textContent = texto.value.length + " / 500 caracteres";
    };
    if (texto) { texto.addEventListener("input", actualizar); actualizar(); }
    formulario.addEventListener("submit", function () {
      var boton = document.getElementById("boton-analizar");
      if (boton) { boton.disabled = true; boton.textContent = "Interpretando…"; }
    });
  }

  var agregar = document.getElementById("agregar-fila");
  var contenedor = document.getElementById("filas");
  if (agregar && contenedor) {
    var prefijo = contenedor.dataset.prefijo;
    var total = document.getElementById("id_" + prefijo + "-TOTAL_FORMS");
    agregar.addEventListener("click", function () {
      var filas = contenedor.querySelectorAll(".fila-formset");
      if (!filas.length || !total) return;
      var indice = parseInt(total.value, 10);
      var copia = filas[filas.length - 1].cloneNode(true);
      var patron = new RegExp(prefijo + "-\\d+-", "g");
      copia.querySelectorAll("input, select, label").forEach(function (el) {
        ["name", "id", "for"].forEach(function (attr) {
          if (el.getAttribute(attr)) el.setAttribute(attr, el.getAttribute(attr).replace(patron, prefijo + "-" + indice + "-"));
        });
        if (el.tagName === "INPUT" && el.type !== "checkbox") el.value = "";
        if (el.type === "checkbox") el.checked = false;
        if (el.tagName === "SELECT") el.selectedIndex = 0;
      });
      copia.querySelectorAll(".error").forEach(function (e) { e.remove(); });
      contenedor.appendChild(copia);
      total.value = indice + 1;
      var primero = copia.querySelector("input");
      if (primero) primero.focus();
    });
  }
})();
