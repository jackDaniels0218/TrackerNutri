/*
  Pequeñas ayudas de los formularios.

  Dos cosas, nada más:
  1. Mostrar "Analizando…" mientras el servidor habla con la IA, para que el
     usuario sepa que la espera es normal.
  2. Añadir filas de alimentos en el registro manual, clonando la última fila
     y actualizando los índices que exige el formset de Django.

  Si JavaScript está desactivado, los formularios siguen funcionando: el
  análisis se envía igual y el formset ya trae una fila lista.
*/

(function () {
  "use strict";

  // --- 1. Estado de carga al analizar con IA -------------------------------
  var formularioAnalisis = document.getElementById("formulario-analisis");
  if (formularioAnalisis) {
    formularioAnalisis.addEventListener("submit", function () {
      var boton = document.getElementById("boton-analizar");
      var indicador = document.getElementById("indicador-carga");
      if (boton) {
        boton.disabled = true;
        boton.textContent = "Analizando…";
      }
      if (indicador) indicador.classList.remove("oculto");
    });
  }

  // --- 2. Añadir filas en el registro manual -------------------------------
  var botonAgregar = document.getElementById("boton-agregar-fila");
  var cuerpoTabla = document.getElementById("cuerpo-alimentos");
  if (!botonAgregar || !cuerpoTabla) return;

  // Django lleva la cuenta de las filas en este campo oculto.
  var totalFormularios = document.querySelector("#id_form-TOTAL_FORMS");
  if (!totalFormularios) return;

  botonAgregar.addEventListener("click", function () {
    var filas = cuerpoTabla.querySelectorAll("tr.fila-alimento");
    if (!filas.length) return;

    var indiceNuevo = parseInt(totalFormularios.value, 10);
    var copia = filas[filas.length - 1].cloneNode(true);

    // Renumera name/id de "form-0-campo" a "form-N-campo" y limpia valores.
    copia.querySelectorAll("input, select").forEach(function (campo) {
      if (campo.name) {
        campo.name = campo.name.replace(/form-\d+-/, "form-" + indiceNuevo + "-");
      }
      if (campo.id) {
        campo.id = campo.id.replace(/form-\d+-/, "form-" + indiceNuevo + "-");
      }
      if (campo.type === "checkbox") {
        campo.checked = false;
      } else if (campo.tagName === "SELECT") {
        campo.selectedIndex = 0;
      } else {
        campo.value = "";
      }
    });
    copia.querySelectorAll("small.error").forEach(function (e) { e.remove(); });

    cuerpoTabla.appendChild(copia);
    totalFormularios.value = indiceNuevo + 1;
  });
})();
