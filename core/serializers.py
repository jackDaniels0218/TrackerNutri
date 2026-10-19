"""
Serializadores de la API REST.

Traducen entre los modelos de Django y el JSON que consume el frontend.
También validan la entrada: un POST a la API pasa por los mismos controles
que un formulario de la web.
"""

from rest_framework import serializers

from core.models import (
    Alimento,
    DetalleComida,
    MetodoPreparacion,
    PerfilNutricional,
    RegistroComida,
    Unidad,
)
from core.services.nutrition import CantidadInvalida, validar_cantidad


class AlimentoSerializer(serializers.ModelSerializer):
    """Ficha del catálogo tal como la necesita el buscador de alimentos."""

    etiqueta = serializers.SerializerMethodField()
    preparacion = serializers.CharField(
        source="get_metodo_preparacion_display", read_only=True
    )

    class Meta:
        model = Alimento
        fields = (
            "id",
            "nombre",
            "etiqueta",
            "categoria",
            "unidad_referencia",
            "calorias",
            "proteinas",
            "carbohidratos",
            "grasas",
            "metodo_preparacion",
            "preparacion",
            "gramos_por_unidad",
            "descripcion_porcion",
            "fuente",
            "valores_aproximados",
        )

    def get_etiqueta(self, obj) -> str:
        return str(obj)


class PerfilSerializer(serializers.ModelSerializer):
    """Perfil del usuario autenticado. El usuario no se puede cambiar."""

    usuario = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = PerfilNutricional
        fields = (
            "usuario",
            "edad",
            "peso_kg",
            "estatura_cm",
            "meta_calorias_diaria",
            "actualizado_en",
        )
        read_only_fields = ("usuario", "actualizado_en")

    def validate_meta_calorias_diaria(self, valor):
        if valor < 800 or valor > 6000:
            raise serializers.ValidationError(
                "La meta debe estar entre 800 y 6000 kcal."
            )
        return valor


class DetalleComidaSerializer(serializers.ModelSerializer):
    """Una fila de la comida, con lo ya calculado y sin exponer el catálogo."""

    class Meta:
        model = DetalleComida
        fields = (
            "id",
            "alimento",
            "nombre_mostrado",
            "cantidad",
            "unidad",
            "metodo_preparacion",
            "cantidad_base",
            "calorias",
            "proteinas",
            "carbohidratos",
            "grasas",
            "es_estimado",
            "necesita_confirmacion",
            "observacion",
        )
        read_only_fields = fields


class RegistroComidaSerializer(serializers.ModelSerializer):
    """Comida completa de solo lectura, con sus detalles y totales."""

    detalles = DetalleComidaSerializer(many=True, read_only=True)
    totales = serializers.SerializerMethodField()

    class Meta:
        model = RegistroComida
        fields = (
            "id",
            "descripcion",
            "fecha",
            "hora",
            "origen",
            "confirmado",
            "creado_en",
            "detalles",
            "totales",
        )
        read_only_fields = fields

    def get_totales(self, obj) -> dict:
        return obj.totales()


class FilaComidaSerializer(serializers.Serializer):
    """
    Una fila que llega al crear o editar una comida por la API.

    `alimento` puede ser null: significa que no hay coincidencia en el
    catálogo. En ese caso el detalle se guarda sin valores nutricionales.
    """

    alimento = serializers.PrimaryKeyRelatedField(
        queryset=Alimento.objects.filter(activo=True),
        required=False,
        allow_null=True,
    )
    nombre_mostrado = serializers.CharField(max_length=120)
    cantidad = serializers.DecimalField(max_digits=8, decimal_places=2)
    unidad = serializers.ChoiceField(choices=Unidad.choices)
    metodo_preparacion = serializers.ChoiceField(
        choices=MetodoPreparacion.choices,
        required=False,
        default=MetodoPreparacion.NO_ESPECIFICADA,
    )

    def validate_cantidad(self, valor):
        try:
            return validar_cantidad(valor)
        except CantidadInvalida as exc:
            raise serializers.ValidationError(str(exc)) from exc


class CrearComidaSerializer(serializers.Serializer):
    """Entrada de POST /api/comidas/."""

    descripcion = serializers.CharField(max_length=300)
    fecha = serializers.DateField()
    hora = serializers.TimeField(required=False, allow_null=True)
    origen = serializers.ChoiceField(
        choices=["ia", "manual"], required=False, default="manual"
    )
    filas = FilaComidaSerializer(many=True)

    def validate_filas(self, valor):
        if not valor:
            raise serializers.ValidationError(
                "La comida debe incluir al menos un alimento."
            )
        return valor


class AnalizarTextoSerializer(serializers.Serializer):
    """Entrada de POST /api/analizar/."""

    texto = serializers.CharField(max_length=500)

    def validate_texto(self, valor):
        valor = valor.strip()
        if len(valor) < 3:
            raise serializers.ValidationError("Describe la comida con más detalle.")
        return valor
