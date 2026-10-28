"""
API REST v1 (RNF30): la interfaz que consumiría la aplicación móvil.

Usa los mismos servicios que la web, así que las reglas son idénticas. Todas
las rutas exigen sesión iniciada y filtran por el usuario autenticado; las
del catálogo son de solo lectura.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.serializers import (
    AlimentoSerializer,
    ComidaManualSerializer,
    ComidaSerializer,
    InterpretarSerializer,
    MetaSerializer,
    NotificacionSerializer,
    PerfilSerializer,
    PesajeSerializer,
    PreparacionSerializer,
)
from core.models import Comida, EstadoComida, MetaCalorica, MetodoCoccion, Notificacion, Pesaje, Preparacion, Rol
from core.services import comidas as servicio
from core.services import reportes
from core.services.calculo import CantidadInvalida
from core.services.catalogo import alimentos_visibles


class EsUsuario(permissions.BasePermission):
    message = "Solo disponible para el rol Usuario."

    def has_permission(self, request, view):
        cuenta = getattr(request.user, "cuenta", None)
        return bool(request.user.is_authenticated and cuenta and cuenta.rol == Rol.USUARIO)


class PerfilView(generics.RetrieveAPIView):
    """Perfil del usuario autenticado (solo lectura; se edita desde la app)."""

    serializer_class = PerfilSerializer
    permission_classes = [EsUsuario]

    def get_object(self):
        from core.models import PerfilNutricional

        return get_object_or_404(PerfilNutricional, usuario=self.request.user)


class AlimentosView(generics.ListAPIView):
    """Catálogo global más los alimentos personales del usuario. ?buscar=arepa"""

    serializer_class = AlimentoSerializer

    def get_queryset(self):
        lista = alimentos_visibles(self.request.user)
        if self.request.query_params.get("buscar"):
            lista = lista.filter(nombre__icontains=self.request.query_params["buscar"])
        return lista.order_by("nombre")[:100]


class PreparacionesView(generics.ListAPIView):
    serializer_class = PreparacionSerializer

    def get_queryset(self):
        lista = Preparacion.objects.filter(estado="activo").select_related("metodo_defecto")
        if self.request.query_params.get("buscar"):
            lista = lista.filter(nombre__icontains=self.request.query_params["buscar"])
        return lista


class InterpretarView(APIView):
    """
    POST {"texto": "una arepa frita y una gaseosa"}

    Crea la comida en estado «interpretada» y devuelve sus componentes con
    cantidad, método, energía, rango, confianza y las preguntas de
    aclaración. No cuenta en los totales hasta confirmarla.
    """

    permission_classes = [EsUsuario]
    serializer_class = InterpretarSerializer

    def post(self, request):
        entrada = InterpretarSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        comida = servicio.crear_desde_texto(request.user, entrada.validated_data["texto"],
                                            fecha_hora=entrada.validated_data.get("fecha_hora"))
        datos = ComidaSerializer(comida).data
        datos["avisos"] = getattr(comida, "avisos_interpretacion", [])
        return Response(datos, status=status.HTTP_201_CREATED)


class ComidasView(APIView):
    """GET ?fecha=AAAA-MM-DD → comidas del día. POST → registro manual (idempotente)."""

    permission_classes = [EsUsuario]
    serializer_class = ComidaManualSerializer

    def get(self, request):
        texto = request.query_params.get("fecha")
        try:
            fecha = timezone.datetime.strptime(texto, "%Y-%m-%d").date() if texto else timezone.localdate()
        except ValueError:
            return Response({"fecha": "Formato esperado: AAAA-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        comidas = Comida.objects.filter(usuario=request.user, fecha_hora__date=fecha).que_cuentan().prefetch_related("items__metodo")
        return Response(ComidaSerializer(comidas, many=True).data)

    def post(self, request):
        entrada = ComidaManualSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        filas = []
        for fila in entrada.validated_data["filas"]:
            if fila.get("alimento_id"):
                destino = alimentos_visibles(request.user).filter(pk=fila["alimento_id"]).first()
            else:
                destino = Preparacion.objects.filter(pk=fila["preparacion_id"], estado="activo").first()
            if destino is None:
                return Response({"filas": "Algún alimento o preparación no existe."}, status=status.HTTP_400_BAD_REQUEST)
            metodo = MetodoCoccion.objects.filter(clave=fila.get("metodo")).first() if fila.get("metodo") else None
            filas.append({"destino": destino, "cantidad_g": fila["cantidad_g"], "metodo": metodo})
        try:
            comida = servicio.crear_manual(request.user, filas, fecha_hora=entrada.validated_data.get("fecha_hora"),
                                           tipo=entrada.validated_data["tipo"],
                                           clave_idempotencia=entrada.validated_data.get("clave_idempotencia"))
        except CantidadInvalida as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ComidaSerializer(comida).data, status=status.HTTP_201_CREATED)


class ComidaView(APIView):
    """GET una comida; DELETE la descarta (baja lógica)."""

    permission_classes = [EsUsuario]

    def _comida(self, request, pk):
        return get_object_or_404(Comida.objects.filter(usuario=request.user), pk=pk)

    def get(self, request, pk):
        return Response(ComidaSerializer(self._comida(request, pk)).data)

    def delete(self, request, pk):
        servicio.descartar(self._comida(request, pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConfirmarComidaView(APIView):
    permission_classes = [EsUsuario]

    def post(self, request, pk):
        comida = get_object_or_404(Comida.objects.filter(usuario=request.user, estado=EstadoComida.INTERPRETADA), pk=pk)
        if request.data.get("respuestas"):
            servicio.responder_preguntas(comida, request.data["respuestas"])
        try:
            servicio.confirmar(comida)
        except servicio.ComidaNoConfirmable as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(ComidaSerializer(comida).data)


class ResumenView(APIView):
    permission_classes = [EsUsuario]

    def get(self, request):
        texto = request.query_params.get("fecha")
        try:
            fecha = timezone.datetime.strptime(texto, "%Y-%m-%d").date() if texto else timezone.localdate()
        except ValueError:
            return Response({"fecha": "Formato esperado: AAAA-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        resumen = reportes.resumen_dia(request.user, fecha)
        resumen.pop("comidas")
        meta = resumen.pop("meta")
        resumen["meta_id"] = meta.pk if meta else None
        return Response(resumen)


class SeriesView(APIView):
    permission_classes = [EsUsuario]

    def get(self, request):
        try:
            dias = int(request.query_params.get("dias", 30))
        except ValueError:
            dias = 30
        return Response(reportes.series(request.user, dias))


class PesajesView(generics.ListCreateAPIView):
    serializer_class = PesajeSerializer
    permission_classes = [EsUsuario]

    def get_queryset(self):
        return Pesaje.objects.filter(usuario=self.request.user)

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)


class MetasView(generics.ListAPIView):
    serializer_class = MetaSerializer
    permission_classes = [EsUsuario]

    def get_queryset(self):
        return MetaCalorica.objects.filter(usuario=self.request.user).order_by("-creada_en")


class NotificacionesView(generics.ListAPIView):
    serializer_class = NotificacionSerializer

    def get_queryset(self):
        return Notificacion.objects.filter(destinatario=self.request.user)[:100]

