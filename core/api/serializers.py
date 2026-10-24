"""Serializadores de la API REST v1."""

from decimal import Decimal

from rest_framework import serializers

from core.models import (
    Alimento,
    Comida,
    ItemComida,
    MetaCalorica,
    Notificacion,
    PerfilNutricional,
    Pesaje,
    Preparacion,
)


class PerfilSerializer(serializers.ModelSerializer):
    edad = serializers.IntegerField(read_only=True)

    class Meta:
        model = PerfilNutricional
        fields = ("fecha_nacimiento", "edad", "sexo", "estatura_cm", "peso_inicial_kg", "nivel_actividad", "objetivo",
                  "peso_meta_kg", "ritmo", "gestante_lactante", "requiere_acompanamiento", "ocultar_cifras")


class AlimentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alimento
        fields = ("id", "nombre", "categoria", "estado_fisico", "kcal", "proteinas", "carbohidratos", "azucares",
                  "grasas", "fibra", "sodio_mg", "densidad", "fuente", "verificado", "ambito")


class PreparacionSerializer(serializers.ModelSerializer):
    metodo_defecto = serializers.CharField(source="metodo_defecto.clave")

    class Meta:
        model = Preparacion
        fields = ("id", "nombre", "categoria", "region", "peso_porcion_g", "metodo_defecto", "verificada")


class ItemSerializer(serializers.ModelSerializer):
    metodo = serializers.CharField(source="metodo.clave", default=None)

    class Meta:
        model = ItemComida
        fields = ("id", "nombre_mostrado", "fragmento_texto", "cantidad_g", "fuente_cantidad", "metodo", "origen_metodo",
                  "kcal", "kcal_min", "kcal_max", "proteinas", "carbohidratos", "azucares", "grasas", "aceite_g",
                  "confianza", "origen_dato", "estimado", "editado", "pendiente", "descartado", "detalle_calculo")


class ComidaSerializer(serializers.ModelSerializer):
    items = ItemSerializer(many=True, read_only=True)

    class Meta:
        model = Comida
        fields = ("id", "texto_original", "fecha_hora", "tipo", "origen", "estado", "kcal", "kcal_min", "kcal_max",
                  "proteinas", "carbohidratos", "azucares", "grasas", "aceite_g", "confianza", "motor", "version_motor",
                  "version_catalogo", "preguntas", "es_favorita", "items")


class InterpretarSerializer(serializers.Serializer):
    texto = serializers.CharField(max_length=500, min_length=3)
    fecha_hora = serializers.DateTimeField(required=False)


class FilaManualSerializer(serializers.Serializer):
    alimento_id = serializers.IntegerField(required=False)
    preparacion_id = serializers.IntegerField(required=False)
    cantidad_g = serializers.DecimalField(max_digits=8, decimal_places=1, min_value=Decimal("0.1"), max_value=Decimal("5000"))
    metodo = serializers.CharField(required=False, allow_blank=True)

    def validate(self, datos):
        if bool(datos.get("alimento_id")) == bool(datos.get("preparacion_id")):
            raise serializers.ValidationError("Indica alimento_id o preparacion_id (solo uno).")
        return datos


class ComidaManualSerializer(serializers.Serializer):
    fecha_hora = serializers.DateTimeField(required=False)
    tipo = serializers.CharField(required=False, default="otro")
    clave_idempotencia = serializers.UUIDField(required=False)
    filas = FilaManualSerializer(many=True)


class PesajeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pesaje
        fields = ("id", "fecha", "peso_kg", "observacion")


class MetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetaCalorica
        fields = ("id", "fecha_inicio", "fecha_fin", "vigente", "tmb", "gasto_total", "kcal_dia", "deficit_pct",
                  "proteinas_g", "carbohidratos_g", "grasas_g", "origen", "motivo", "explicacion", "solo_informativa",
                  "revertida", "revertible_hasta")


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = ("id", "tipo", "titulo", "mensaje", "url", "leida", "creada_en")
