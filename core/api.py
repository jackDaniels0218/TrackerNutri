"""
Endpoints de la API REST (Django REST Framework).

Solo existen los que aportan algo que las páginas normales no resuelven mejor:
buscar alimentos mientras se escribe, analizar texto con IA, y leer el resumen
y el historial desde JavaScript.

Todos exigen sesión iniciada (REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES) y
todos filtran por el usuario autenticado.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Alimento, RegistroComida
from core.serializers import (
    AlimentoSerializer,
    AnalizarTextoSerializer,
    CrearComidaSerializer,
    PerfilSerializer,
    RegistroComidaSerializer,
)
from core.services import ai_service
from core.services.comidas import guardar_comida, reemplazar_detalles
from core.services.nutrition import CantidadInvalida, resumen_diario


def _fecha_o_hoy(request):
    """Lee ?fecha=AAAA-MM-DD; si falta o no es válida, devuelve hoy."""
    texto = request.query_params.get("fecha")
    if not texto:
        return timezone.localdate()
    try:
        return timezone.datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError({"fecha": "Formato esperado: AAAA-MM-DD."}) from exc


class AlimentoListView(generics.ListAPIView):
    """
    GET /api/alimentos/?buscar=arepa

    Lo usa el buscador del formulario manual.
    """

    serializer_class = AlimentoSerializer

    def get_queryset(self):
        queryset = Alimento.objects.filter(activo=True)
        buscar = self.request.query_params.get("buscar")
        if buscar:
            queryset = queryset.filter(nombre__icontains=buscar)
        return queryset.order_by("nombre", "metodo_preparacion")


class PerfilView(generics.RetrieveUpdateAPIView):
    """GET y PATCH /api/perfil/ del usuario autenticado."""

    serializer_class = PerfilSerializer

    def get_object(self):
        return self.request.user.perfil


class AnalizarComidaView(APIView):
    """
    POST /api/analizar/  {"texto": "una arepa frita y dos huevos"}

    Devuelve los alimentos detectados y emparejados con el catálogo, SIN
    guardarlos: el usuario todavía tiene que confirmarlos.

    Cuando la IA no está disponible devuelve 503 con un mensaje legible y
    `modo_manual_disponible: true`, para que el frontend ofrezca la
    alternativa en lugar de mostrar un error genérico.
    """

    def post(self, request):
        entrada = AnalizarTextoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        try:
            items = ai_service.analizar_texto(entrada.validated_data["texto"])
        except ai_service.ErrorIA as exc:
            codigo = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if isinstance(exc, (ai_service.IANoDisponible, ai_service.IANoConfigurada))
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            )
            return Response(
                {
                    "error": exc.mensaje_usuario,
                    "tipo": type(exc).__name__,
                    "modo_manual_disponible": True,
                },
                status=codigo,
            )

        # El objeto Alimento no es serializable: se envía solo su id y etiqueta.
        respuesta = []
        for item in items:
            alimento = item.pop("alimento", None)
            respuesta.append(
                {
                    **item,
                    "alimento_etiqueta": str(alimento) if alimento else None,
                }
            )
        return Response({"items": respuesta})


class ComidaListCreateView(APIView):
    """
    GET  /api/comidas/?fecha=AAAA-MM-DD  -> comidas de ese día
    POST /api/comidas/                   -> crea una comida con sus filas
    """

    def get(self, request):
        fecha = _fecha_o_hoy(request)
        comidas = RegistroComida.objects.filter(
            usuario=request.user, fecha=fecha
        ).prefetch_related("detalles")
        return Response(RegistroComidaSerializer(comidas, many=True).data)

    def post(self, request):
        entrada = CrearComidaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        try:
            registro = guardar_comida(
                request.user,
                descripcion=datos["descripcion"],
                fecha=datos["fecha"],
                hora=datos.get("hora"),
                filas=datos["filas"],
                origen=datos.get("origen", "manual"),
                confirmado=True,
            )
        except CantidadInvalida as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            RegistroComidaSerializer(registro).data, status=status.HTTP_201_CREATED
        )


class ComidaDetailView(APIView):
    """
    GET / PUT / DELETE de una comida concreta.

    `_obtener` filtra por usuario, así que pedir la comida de otra persona
    devuelve 404 en lugar de exponerla.
    """

    def _obtener(self, request, pk):
        return get_object_or_404(RegistroComida, pk=pk, usuario=request.user)

    def get(self, request, pk):
        return Response(RegistroComidaSerializer(self._obtener(request, pk)).data)

    def put(self, request, pk):
        comida = self._obtener(request, pk)
        entrada = CrearComidaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        comida.descripcion = datos["descripcion"]
        comida.fecha = datos["fecha"]
        comida.hora = datos.get("hora")
        comida.save()

        try:
            reemplazar_detalles(comida, datos["filas"])
        except CantidadInvalida as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(RegistroComidaSerializer(comida).data)

    def delete(self, request, pk):
        self._obtener(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def resumen_dia(request):
    """
    GET /api/resumen/?fecha=AAAA-MM-DD

    Devuelve el mismo resumen que muestra el panel. Lo usa Chart.js.
    """
    fecha = _fecha_o_hoy(request)
    return Response(resumen_diario(request.user, fecha))


@api_view(["GET"])
def tendencia(request):
    """
    GET /api/tendencia/?dias=7

    Calorías confirmadas por día para el gráfico de evolución.
    """
    try:
        dias = min(max(int(request.query_params.get("dias", 7)), 1), 31)
    except (TypeError, ValueError):
        dias = 7

    hoy = timezone.localdate()
    resultado = []
    for i in range(dias - 1, -1, -1):
        fecha = hoy - timedelta(days=i)
        resumen = resumen_diario(request.user, fecha)
        resultado.append(
            {
                "fecha": fecha.isoformat(),
                "calorias": resumen["consumido"],
                "meta": resumen["meta"],
            }
        )
    return Response({"dias": resultado})
