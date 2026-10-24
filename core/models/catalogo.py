"""
Catálogo nutricional: RF3 Alimentos base, RF4 Preparaciones y componentes,
RF5 Métodos de cocción y absorción, RF6 Léxico y porciones caseras, y el
versionado e historial que exige RF19 y RF22.

Todos los valores de composición están POR 100 g. Los líquidos usan la
densidad (g/ml) para convertir mililitros a gramos, como pide el SRS.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

CERO = Decimal("0")
CIEN = Decimal("100")
NO_NEGATIVO = [MinValueValidator(CERO)]
MAX_100 = [MinValueValidator(CERO), MaxValueValidator(CIEN)]


class EstadoRegistro(models.TextChoices):
    """Baja lógica: lo que tiene historial se inactiva, no se borra."""

    ACTIVO = "activo", "Activo"
    INACTIVO = "inactivo", "Inactivo"


# --- Versionado -------------------------------------------------------------


class VersionCatalogo(models.Model):
    """
    Cada conjunto de cambios del Curador genera una versión (actividad 19).

    Solo hay una versión en borrador a la vez; al publicarla se ejecuta el
    conjunto de pruebas de exactitud y, si no supera los umbrales, se bloquea.
    """

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PUBLICADA = "publicada", "Publicada"
        RECHAZADA = "rechazada", "Bloqueada por exactitud"

    numero = models.PositiveIntegerField(unique=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.BORRADOR)
    notas = models.TextField(blank=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    publicada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-numero"]
        verbose_name = "versión del catálogo"
        verbose_name_plural = "versiones del catálogo"

    def __str__(self) -> str:
        return f"v{self.numero} ({self.get_estado_display().lower()})"

    @classmethod
    def publicada_vigente(cls):
        return cls.objects.filter(estado=cls.Estado.PUBLICADA).order_by("-numero").first()

    @classmethod
    def borrador(cls):
        """Devuelve la versión en borrador; la crea si no existe."""
        actual = cls.objects.filter(estado=cls.Estado.BORRADOR).first()
        if actual:
            return actual
        ultima = cls.objects.order_by("-numero").first()
        return cls.objects.create(numero=(ultima.numero + 1) if ultima else 1)


# --- Métodos de cocción y absorción (actividad 5) ---------------------------


class MetodoCoccion(models.Model):
    """
    Forma de preparar un alimento y cómo cambia su peso y su grasa.

    factor_agua: % de cambio de peso al cocinar (negativo = pierde agua, como
    al asar; positivo = gana agua, como el arroz al hervir).
    perdida_grasa: % de la grasa del alimento que se pierde al cocinar (cortes
    asados que gotean).
    """

    clave = models.SlugField(max_length=30, unique=True)
    nombre = models.CharField(max_length=60, unique=True)
    usa_grasa = models.BooleanField(default=False)
    es_fritura = models.BooleanField(
        default=False, help_text="Activa la calculadora de absorción de aceite."
    )
    factor_agua = models.DecimalField(
        max_digits=5, decimal_places=1, default=CERO,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("300"))],
    )
    perdida_grasa = models.DecimalField(max_digits=5, decimal_places=1, default=CERO, validators=MAX_100)
    palabras = models.TextField(
        help_text="Palabras que lo identifican en el texto, separadas por comas."
    )
    estado = models.CharField(max_length=10, choices=EstadoRegistro.choices, default=EstadoRegistro.ACTIVO)
    version = models.ForeignKey(VersionCatalogo, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "método de cocción"
        verbose_name_plural = "métodos de cocción"

    def __str__(self) -> str:
        return self.nombre

    def lista_palabras(self) -> list[str]:
        return [p.strip() for p in self.palabras.split(",") if p.strip()]

    def delete(self, *args, **kwargs):
        raise ValidationError("Los métodos de cocción no se eliminan: se inactivan.")


class Matriz(models.TextChoices):
    """Tipo de alimento a efectos de cuánto aceite absorbe."""

    MASA_MAIZ = "masa_maiz", "Masa de maíz"
    MASA_TRIGO = "masa_trigo", "Masa de trigo"
    APANADO = "apanado", "Apanado o empanizado"
    TUBERCULO = "tuberculo", "Tubérculo o plátano"
    CARNE = "carne", "Carne sin apanar"
    PESCADO = "pescado", "Pescado"
    HUEVO = "huevo", "Huevo"
    OTRO = "otro", "Otro"


class CoeficienteAbsorcion(models.Model):
    """% de aceite absorbido sobre el peso crudo: mínimo, típico y máximo."""

    metodo = models.ForeignKey(MetodoCoccion, on_delete=models.PROTECT, related_name="coeficientes")
    matriz = models.CharField(max_length=15, choices=Matriz.choices)
    pct_min = models.DecimalField(max_digits=5, decimal_places=1, validators=MAX_100)
    pct_tipico = models.DecimalField(max_digits=5, decimal_places=1, validators=MAX_100)
    pct_max = models.DecimalField(max_digits=5, decimal_places=1, validators=MAX_100)
    fuente = models.CharField(max_length=250)
    estado = models.CharField(max_length=10, choices=EstadoRegistro.choices, default=EstadoRegistro.ACTIVO)
    version = models.ForeignKey(VersionCatalogo, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        ordering = ["metodo__nombre", "matriz"]
        verbose_name = "coeficiente de absorción"
        verbose_name_plural = "coeficientes de absorción"
        constraints = [
            models.UniqueConstraint(fields=["metodo", "matriz"], name="coeficiente_unico")
        ]

    def __str__(self) -> str:
        return f"{self.metodo} · {self.get_matriz_display()}: {self.pct_tipico} %"

    def clean(self):
        if self.pct_min is not None and self.pct_tipico is not None and self.pct_max is not None:
            if not (self.pct_min <= self.pct_tipico <= self.pct_max):
                raise ValidationError("Debe cumplirse mínimo ≤ típico ≤ máximo.")

    def delete(self, *args, **kwargs):
        raise ValidationError("Los coeficientes no se eliminan: se inactivan.")


# --- Alimentos base (actividad 3) -------------------------------------------


class EstadoFisico(models.TextChoices):
    CRUDO = "crudo", "Crudo"
    COCIDO = "cocido", "Cocido o listo para consumir"


class FuenteDato(models.TextChoices):
    TCAC = "tcac", "TCAC (ICBF)"
    USDA = "usda", "USDA FoodData Central"
    ETIQUETA = "etiqueta", "Etiqueta nutricional"
    ESTIMADO = "estimado", "Estimado por el Curador"


class Ambito(models.TextChoices):
    GLOBAL = "global", "Catálogo global"
    PERSONAL = "personal", "Personal del usuario"


class Alimento(models.Model):
    """
    Alimento base del catálogo o alimento personal de un usuario.

    Los nutrientes que no se conocen quedan en NULL, nunca en cero: un cero
    afirmaría que el alimento no tiene ese nutriente.
    """

    nombre = models.CharField(max_length=120)
    categoria = models.CharField(max_length=60)
    estado_fisico = models.CharField(max_length=10, choices=EstadoFisico.choices)
    kcal = models.DecimalField(max_digits=6, decimal_places=1, validators=NO_NEGATIVO, verbose_name="energía (kcal)")
    proteinas = models.DecimalField(max_digits=5, decimal_places=1, validators=MAX_100)
    carbohidratos = models.DecimalField(max_digits=5, decimal_places=1, validators=MAX_100)
    azucares = models.DecimalField(max_digits=5, decimal_places=1, validators=MAX_100, null=True, blank=True)
    grasas = models.DecimalField(max_digits=5, decimal_places=1, validators=MAX_100)
    grasas_saturadas = models.DecimalField(max_digits=5, decimal_places=1, validators=MAX_100, null=True, blank=True)
    fibra = models.DecimalField(max_digits=5, decimal_places=1, validators=MAX_100, null=True, blank=True)
    sodio_mg = models.DecimalField(max_digits=7, decimal_places=1, validators=NO_NEGATIVO, null=True, blank=True)
    agua_pct = models.DecimalField(max_digits=4, decimal_places=1, validators=MAX_100, null=True, blank=True)
    densidad = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.1")), MaxValueValidator(Decimal("3"))],
        help_text="g/ml. Solo para líquidos: convierte mililitros a gramos.",
    )
    rendimiento_pct = models.DecimalField(
        max_digits=4, decimal_places=1, validators=MAX_100, null=True, blank=True,
        help_text="Parte comestible, para cortes de carne con hueso.",
    )
    grasa_visible_pct = models.DecimalField(
        max_digits=4, decimal_places=1, validators=MAX_100, null=True, blank=True,
        help_text="Grasa visible que suele retirarse, para cortes de carne.",
    )
    matriz = models.CharField(
        max_length=15, choices=Matriz.choices, default=Matriz.OTRO,
        help_text="Tipo de alimento para la calculadora de absorción de aceite.",
    )
    metodo_defecto = models.ForeignKey(
        MetodoCoccion, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        help_text="Para alimentos crudos: cómo se suele preparar si el usuario no lo dice.",
    )
    ambito = models.CharField(max_length=10, choices=Ambito.choices, default=Ambito.GLOBAL)
    propietario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="alimentos_personales",
    )
    fuente = models.CharField(max_length=10, choices=FuenteDato.choices, default=FuenteDato.ESTIMADO)
    fuente_detalle = models.CharField(max_length=250, blank=True)
    verificado = models.BooleanField(default=False)
    estado = models.CharField(max_length=10, choices=EstadoRegistro.choices, default=EstadoRegistro.ACTIVO)
    version = models.ForeignKey(VersionCatalogo, on_delete=models.PROTECT, null=True, blank=True)
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    modificado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "alimento base"
        verbose_name_plural = "alimentos base"
        indexes = [models.Index(fields=["ambito", "estado"], name="idx_alimento_ambito")]

    def __str__(self) -> str:
        return self.nombre

    @property
    def es_liquido(self) -> bool:
        return self.densidad is not None

    def kcal_atwater(self) -> Decimal:
        """Energía calculada con los factores de Atwater (4, 4 y 9 kcal/g)."""
        return self.proteinas * 4 + self.carbohidratos * 4 + self.grasas * 9

    def clean(self):
        from core.services.parametros import parametro

        errores = {}
        macros = [v for v in (self.proteinas, self.carbohidratos, self.grasas) if v is not None]
        if len(macros) == 3:
            if sum(macros) > CIEN:
                errores["carbohidratos"] = "Proteínas, carbohidratos y grasas no pueden sumar más de 100 g."
            if self.kcal is not None:
                calculada = self.kcal_atwater()
                tolerancia = parametro("tolerancia_atwater_pct") / 100
                referencia = max(self.kcal, Decimal("20"))
                if abs(self.kcal - calculada) > referencia * tolerancia:
                    errores["kcal"] = (
                        f"La energía declarada ({self.kcal} kcal) no coincide con la "
                        f"calculada por Atwater ({calculada:.0f} kcal)."
                    )
        if self.azucares is not None and self.carbohidratos is not None and self.azucares > self.carbohidratos:
            errores["azucares"] = "Los azúcares no pueden superar a los carbohidratos."
        if self.ambito == Ambito.PERSONAL and not self.propietario_id:
            errores["propietario"] = "Un alimento personal necesita propietario."
        if errores:
            raise ValidationError(errores)

    def delete(self, *args, **kwargs):
        if self.itemcomida_set.exists() or self.componentes.exists():
            raise ValidationError("Un alimento con registros asociados no se elimina: se inactiva.")
        super().delete(*args, **kwargs)


# --- Preparaciones regionales (actividad 4) ---------------------------------


class CategoriaPreparacion(models.TextChoices):
    DESAYUNO = "desayuno", "Desayuno"
    PLATO_FUERTE = "plato_fuerte", "Plato fuerte"
    SOPA = "sopa", "Sopa"
    FRITURA = "fritura", "Fritura"
    BEBIDA = "bebida", "Bebida"
    POSTRE = "postre", "Postre"
    PASABOCAS = "pasabocas", "Pasabocas"
    OTRA = "otra", "Otra"


class Preparacion(models.Model):
    """Preparación regional que se deconstruye en ingredientes crudos."""

    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(blank=True)
    region = models.CharField(max_length=60, default="Andina")
    categoria = models.CharField(max_length=15, choices=CategoriaPreparacion.choices)
    peso_porcion_g = models.DecimalField(
        max_digits=6, decimal_places=1, validators=[MinValueValidator(Decimal("1"))],
        help_text="Peso de la porción típica ya preparada.",
    )
    metodo_defecto = models.ForeignKey(MetodoCoccion, on_delete=models.PROTECT, related_name="+")
    admite_variantes = models.BooleanField(
        default=False,
        help_text="Si se prepara de varias formas (arepa asada o frita), se pregunta cuando no se dice.",
    )
    verificada = models.BooleanField(default=False)
    estado = models.CharField(max_length=10, choices=EstadoRegistro.choices, default=EstadoRegistro.ACTIVO)
    version = models.ForeignKey(VersionCatalogo, on_delete=models.PROTECT, null=True, blank=True)
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    modificado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "preparación regional"
        verbose_name_plural = "preparaciones regionales"

    def __str__(self) -> str:
        return self.nombre

    @property
    def es_bebida(self) -> bool:
        return self.categoria == CategoriaPreparacion.BEBIDA

    def peso_estimado_componentes(self) -> Decimal:
        """
        Peso que tendrían los componentes ya cocinados.

        Se usa para validar que la receta es coherente con la porción.
        """
        total = CERO
        for c in self.componentes.filter(opcional=False).select_related("alimento", "metodo"):
            metodo = c.metodo or self.metodo_defecto
            factor = CERO
            if c.alimento.estado_fisico == EstadoFisico.CRUDO and metodo:
                factor = metodo.factor_agua
            total += c.cantidad_g * (1 + factor / 100)
        return total

    def validar_peso(self) -> str:
        """Mensaje de advertencia si la receta no cuadra con la porción, o ''."""
        from core.services.parametros import parametro

        if not self.pk or not self.componentes.exists():
            return ""
        estimado = self.peso_estimado_componentes()
        tolerancia = parametro("tolerancia_peso_preparacion_pct") / 100
        if abs(estimado - self.peso_porcion_g) > self.peso_porcion_g * tolerancia:
            return (
                f"Los componentes cocinados pesan unos {estimado:.0f} g y la porción "
                f"declarada es de {self.peso_porcion_g:.0f} g."
            )
        return ""

    def delete(self, *args, **kwargs):
        if self.itemcomida_set.exists():
            raise ValidationError("Una preparación con ingestas asociadas no se elimina: se inactiva.")
        super().delete(*args, **kwargs)


class RolComponente(models.TextChoices):
    BASE = "base", "Base"
    RELLENO = "relleno", "Relleno"
    ACOMPANANTE = "acompanante", "Acompañante"
    SALSA = "salsa", "Salsa"
    GRASA = "grasa_coccion", "Grasa de cocción"


class Componente(models.Model):
    """Una línea de la receta: cuántos gramos crudos de qué alimento."""

    preparacion = models.ForeignKey(Preparacion, on_delete=models.CASCADE, related_name="componentes")
    alimento = models.ForeignKey(Alimento, on_delete=models.PROTECT, related_name="componentes")
    cantidad_g = models.DecimalField(
        max_digits=6, decimal_places=1, validators=[MinValueValidator(Decimal("0.1"))],
        help_text="Gramos en crudo por porción típica.",
    )
    metodo = models.ForeignKey(
        MetodoCoccion, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
        help_text="Solo si difiere del método de la preparación.",
    )
    rol = models.CharField(max_length=15, choices=RolComponente.choices, default=RolComponente.BASE)
    opcional = models.BooleanField(default=False)

    class Meta:
        ordering = ["preparacion", "id"]

    def __str__(self) -> str:
        return f"{self.alimento} {self.cantidad_g} g"


# --- Léxico y porciones caseras (actividad 6) -------------------------------


class TipoTermino(models.TextChoices):
    ALIMENTO = "alimento", "Alimento"
    PREPARACION = "preparacion", "Preparación"
    METODO = "metodo", "Método de cocción"


class TerminoLexico(models.Model):
    """
    Palabra o expresión que el sistema reconoce, y a qué apunta.

    `termino` es único: impide que el mismo término tenga dos destinos.
    """

    termino = models.CharField(max_length=120, unique=True, help_text="En minúsculas y sin tildes.")
    tipo = models.CharField(max_length=15, choices=TipoTermino.choices)
    alimento = models.ForeignKey(Alimento, on_delete=models.CASCADE, null=True, blank=True, related_name="terminos")
    preparacion = models.ForeignKey(Preparacion, on_delete=models.CASCADE, null=True, blank=True, related_name="terminos")
    metodo = models.ForeignKey(MetodoCoccion, on_delete=models.CASCADE, null=True, blank=True, related_name="terminos")
    region = models.CharField(max_length=60, blank=True)
    estado = models.CharField(max_length=10, choices=EstadoRegistro.choices, default=EstadoRegistro.ACTIVO)

    class Meta:
        ordering = ["termino"]
        verbose_name = "término del léxico"
        verbose_name_plural = "léxico"

    def __str__(self) -> str:
        return f"{self.termino} → {self.destino}"

    @property
    def destino(self):
        return self.alimento or self.preparacion or self.metodo

    def clean(self):
        from core.services.texto import normalizar

        self.termino = normalizar(self.termino)
        destinos = [d for d in (self.alimento_id, self.preparacion_id, self.metodo_id) if d]
        if len(destinos) != 1:
            raise ValidationError("Un término debe apuntar exactamente a un destino.")
        esperado = {
            TipoTermino.ALIMENTO: self.alimento_id,
            TipoTermino.PREPARACION: self.preparacion_id,
            TipoTermino.METODO: self.metodo_id,
        }[self.tipo]
        if not esperado:
            raise ValidationError("El tipo del término no coincide con su destino.")


class PorcionCasera(models.Model):
    """Medida casera ("unidad mediana", "vaso") y su equivalencia en g o ml."""

    class Medida(models.TextChoices):
        UNIDAD_PEQUENA = "unidad_pequena", "Unidad pequeña"
        UNIDAD_MEDIANA = "unidad_mediana", "Unidad mediana"
        UNIDAD_GRANDE = "unidad_grande", "Unidad grande"
        PORCION = "porcion", "Porción"
        PLATO = "plato", "Plato"
        VASO = "vaso", "Vaso"
        TAZA = "taza", "Taza"
        POCILLO = "pocillo", "Pocillo"
        CUCHARADA = "cucharada", "Cucharada"
        CUCHARADITA = "cucharadita", "Cucharadita"
        LATA = "lata", "Lata"
        BOTELLA_PERSONAL = "botella_personal", "Botella personal"
        TAJADA = "tajada", "Tajada"

    alimento = models.ForeignKey(Alimento, on_delete=models.CASCADE, null=True, blank=True, related_name="porciones")
    preparacion = models.ForeignKey(Preparacion, on_delete=models.CASCADE, null=True, blank=True, related_name="porciones")
    medida = models.CharField(max_length=20, choices=Medida.choices)
    cantidad = models.DecimalField(
        max_digits=6, decimal_places=1, validators=[MinValueValidator(Decimal("0.1"))],
        help_text="Gramos (o mililitros en bebidas).",
    )
    por_defecto = models.BooleanField(default=False)

    class Meta:
        ordering = ["medida"]
        verbose_name = "porción casera"
        verbose_name_plural = "porciones caseras"

    def __str__(self) -> str:
        destino = self.alimento or self.preparacion
        return f"{destino}: {self.get_medida_display()} = {self.cantidad}"

    def clean(self):
        if bool(self.alimento_id) == bool(self.preparacion_id):
            raise ValidationError("La porción pertenece a un alimento o a una preparación, no a ambos.")


class TerminoPendiente(models.Model):
    """
    Término que un usuario escribió y el sistema no reconoció.

    Llega a la bandeja del Curador. Solo se guarda el término, nunca quién lo
    escribió ni el resto de la frase.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        RESUELTO = "resuelto", "Incorporado al léxico"
        DESCARTADO = "descartado", "Descartado"

    termino = models.CharField(max_length=120, unique=True)
    veces = models.PositiveIntegerField(default=1)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    primera_vez = models.DateTimeField(auto_now_add=True)
    ultima_vez = models.DateTimeField(auto_now=True)
    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-veces", "-ultima_vez"]
        verbose_name = "término no reconocido"
        verbose_name_plural = "términos no reconocidos"

    def __str__(self) -> str:
        return f"{self.termino} ({self.veces})"


class HistorialCatalogo(models.Model):
    """Cada cambio al catálogo, con valor anterior y nuevo. Solo inserción."""

    version = models.ForeignKey(VersionCatalogo, on_delete=models.PROTECT, related_name="cambios")
    entidad = models.CharField(max_length=40)
    entidad_id = models.PositiveIntegerField()
    descripcion = models.CharField(max_length=200)
    valor_anterior = models.JSONField(null=True, blank=True)
    valor_nuevo = models.JSONField(null=True, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    fecha = models.DateTimeField(auto_now_add=True)
    revertido = models.BooleanField(default=False)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "cambio del catálogo"
        verbose_name_plural = "historial del catálogo"

    def __str__(self) -> str:
        return f"{self.version} · {self.descripcion}"

    def delete(self, *args, **kwargs):
        raise ValidationError("El historial del catálogo no se puede borrar.")
