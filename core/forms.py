"""
Formularios de NutriRegional.

Aquí vive la validación de lo que escribe cada rol. Ningún dato llega a la
base de datos sin pasar por un formulario o un serializador.
"""

from __future__ import annotations

from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.forms import inlineformset_factory
from django.utils import timezone

from core.models import (
    Alimento,
    CoeficienteAbsorcion,
    Componente,
    Correccion,
    Cuenta,
    FraseReferencia,
    MetodoCoccion,
    Parametro,
    PerfilNutricional,
    Pesaje,
    PorcionCasera,
    Preparacion,
    Rol,
    TerminoLexico,
    TipoComida,
)
from core.services.parametros import parametro, validar_valor
from core.services.texto import normalizar

FECHA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
HORA = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")


class EstiloMixin:
    """Añade la clase CSS a todos los campos para no repetirla en cada plantilla."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
                continue
            campo.widget.attrs.setdefault("class", "campo")


# --- Acceso y registro (RF12) ------------------------------------------------------


class IngresoForm(EstiloMixin, AuthenticationForm):
    """Ingreso con correo y contraseña; respeta el bloqueo temporal."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Correo electrónico"
        self.fields["username"].widget.attrs.update({"autocomplete": "email", "inputmode": "email"})

    def clean(self):
        correo = (self.cleaned_data.get("username") or "").strip().lower()
        self.cleaned_data["username"] = correo
        usuario = get_user_model().objects.filter(username=correo).select_related("cuenta").first()
        cuenta = getattr(usuario, "cuenta", None)
        if cuenta is not None and cuenta.esta_bloqueada:
            raise forms.ValidationError(
                "La cuenta está bloqueada temporalmente por varios intentos fallidos. Inténtalo más tarde "
                "o recupera tu contraseña.", code="bloqueada",
            )
        return super().clean()

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        cuenta = getattr(user, "cuenta", None)
        if cuenta is not None and cuenta.estado != "activo":
            raise forms.ValidationError("Esta cuenta no está activa.", code="inactiva")


class RegistroCuentaForm(EstiloMixin, forms.Form):
    """Paso 1: cuenta y autorizaciones, mostradas por separado."""

    nombres = forms.CharField(max_length=150)
    apellidos = forms.CharField(max_length=150)
    correo = forms.EmailField(label="Correo electrónico")
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput, strip=False,
                                help_text="Mínimo 8 caracteres; no solo números ni una contraseña común.")
    password2 = forms.CharField(label="Repite la contraseña", widget=forms.PasswordInput, strip=False)
    acepta_datos = forms.BooleanField(
        label="Autorizo el tratamiento de mis datos personales, incluidos datos de salud, según la política de tratamiento de datos.",
        required=True,
    )
    acepta_ia = forms.BooleanField(
        label="Autorizo enviar el texto de mis comidas a un proveedor de IA externo (opcional; puede implicar transferencia internacional y lo puedo retirar cuando quiera).",
        required=False,
    )
    entiende_aviso = forms.BooleanField(
        label="Entiendo que NutriRegional no es un servicio médico y no reemplaza a un profesional de la salud.",
        required=True,
    )

    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().lower()
        if get_user_model().objects.filter(username=correo).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo.")
        return correo

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if p1:
            usuario = get_user_model()(username=datos.get("correo", ""), email=datos.get("correo", ""),
                                       first_name=datos.get("nombres", ""), last_name=datos.get("apellidos", ""))
            try:
                password_validation.validate_password(p1, usuario)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return datos


class PerfilForm(EstiloMixin, forms.ModelForm):
    """Paso 2 del registro y edición del perfil (RF2)."""

    class Meta:
        model = PerfilNutricional
        fields = ("fecha_nacimiento", "sexo", "estatura_cm", "peso_inicial_kg", "nivel_actividad", "objetivo",
                  "peso_meta_kg", "ritmo", "gestante_lactante", "requiere_acompanamiento", "ocultar_cifras")
        widgets = {"fecha_nacimiento": FECHA}
        labels = {
            "estatura_cm": "Estatura (cm)",
            "peso_inicial_kg": "Peso actual (kg)",
            "peso_meta_kg": "Peso meta (kg, opcional)",
            "sexo": "Sexo (para la ecuación de la tasa metabólica)",
            "requiere_acompanamiento": "Tengo una condición de salud o de alimentación por la que un profesional me acompaña o debería acompañarme",
        }
        help_texts = {
            "nivel_actividad": "Sedentario: trabajo sentado y poco movimiento. Ligero: caminar a diario. Moderado: ejercicio 3–5 días.",
            "requiere_acompanamiento": "Por ejemplo, diabetes, enfermedad renal o antecedentes de un trastorno de la conducta alimentaria. "
                                       "No te preguntamos cuál: solo nos sirve para no proponerte un déficit.",
        }

    def clean_fecha_nacimiento(self):
        fecha = self.cleaned_data["fecha_nacimiento"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("La fecha no puede ser futura.")
        if PerfilNutricional.calcular_edad(fecha) < 18:
            raise forms.ValidationError("NutriRegional es solo para personas mayores de 18 años.")
        return fecha


class CuentaDatosForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Nombres", "last_name": "Apellidos", "email": "Correo electrónico"}

    def clean_email(self):
        correo = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(username=correo).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo.")
        return correo

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.username = usuario.email
        if commit:
            usuario.save()
        return usuario


class RecordatoriosForm(EstiloMixin, forms.Form):
    hora_1 = forms.TimeField(required=False, widget=HORA, label="Primer recordatorio")
    hora_2 = forms.TimeField(required=False, widget=HORA, label="Segundo recordatorio")
    hora_3 = forms.TimeField(required=False, widget=HORA, label="Tercer recordatorio")
    resumen_semanal = forms.BooleanField(required=False, label="Recibir el resumen semanal por correo")

    def horas(self):
        return sorted({h for h in (self.cleaned_data.get(f"hora_{i}") for i in (1, 2, 3)) if h})


# --- Comidas (RF7, RF13) -------------------------------------------------------------


class ComidaTextoForm(EstiloMixin, forms.Form):
    texto = forms.CharField(
        label="¿Qué comiste?", max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 500, "placeholder":
                                     "Ej.: Hoy almorcé una arepa frita mediana, 150 gramos de carne asada, "
                                     "una porción de arroz y una Coca-Cola de 400 ml"}),
    )
    fecha = forms.DateField(widget=FECHA, initial=timezone.localdate)
    hora = forms.TimeField(widget=HORA, required=False)
    tipo = forms.ChoiceField(choices=[("", "Detectar del texto")] + list(TipoComida.choices), required=False,
                             label="Tipo de comida")

    def clean_texto(self):
        texto = self.cleaned_data["texto"].strip()
        if len(texto) < 3:
            raise forms.ValidationError("Describe la comida con un poco más de detalle.")
        return texto


UNIDADES_MANUALES = [("g", "gramos"), ("ml", "mililitros")] + [
    (m.value, m.label.lower()) for m in PorcionCasera.Medida
]


class FilaManualForm(EstiloMixin, forms.Form):
    """Una fila del registro por búsqueda manual."""

    alimento = forms.CharField(label="Alimento o preparación", max_length=120,
                               widget=forms.TextInput(attrs={"list": "catalogo", "autocomplete": "off"}))
    cantidad = forms.DecimalField(min_value=Decimal("0.01"), max_value=Decimal("5000"), decimal_places=2,
                                  widget=forms.NumberInput(attrs={"step": "0.1", "min": "0.1", "inputmode": "decimal"}))
    unidad = forms.ChoiceField(choices=UNIDADES_MANUALES, initial="g")
    metodo = forms.ModelChoiceField(queryset=MetodoCoccion.objects.filter(estado="activo"), required=False,
                                    empty_label="Como viene en el catálogo", label="Preparación")

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_alimento(self):
        from core.services.catalogo import buscar_por_nombre

        nombre = self.cleaned_data["alimento"]
        destino = buscar_por_nombre(nombre, self.usuario)
        if destino is None:
            raise forms.ValidationError("No está en el catálogo. Elígelo de la lista o créalo como alimento personal.")
        self.cleaned_data["destino"] = destino
        return nombre


class FilaManualFormSet(forms.BaseFormSet):
    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        return {**super().get_form_kwargs(index), "usuario": self.usuario}


FilasManualesFormSet = forms.formset_factory(FilaManualForm, formset=FilaManualFormSet, extra=1, min_num=1,
                                             validate_min=True, can_delete=True)


class ComidaManualForm(EstiloMixin, forms.Form):
    fecha = forms.DateField(widget=FECHA, initial=timezone.localdate)
    hora = forms.TimeField(widget=HORA, required=False)
    tipo = forms.ChoiceField(choices=TipoComida.choices, initial=TipoComida.ALMUERZO, label="Tipo de comida")
    clave = forms.UUIDField(widget=forms.HiddenInput)


class AgregarItemForm(EstiloMixin, forms.Form):
    alimento = forms.CharField(label="Agregar alimento", max_length=120,
                               widget=forms.TextInput(attrs={"list": "catalogo", "autocomplete": "off"}))
    cantidad_g = forms.DecimalField(label="Gramos", min_value=Decimal("0.1"), max_value=Decimal("5000"),
                                    widget=forms.NumberInput(attrs={"step": "1", "min": "1"}))
    metodo = forms.ModelChoiceField(queryset=MetodoCoccion.objects.filter(estado="activo"), required=False,
                                    empty_label="Como viene en el catálogo", label="Preparación")


class CorreccionForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Correccion
        fields = ("tipo", "valor_sugerido", "comentario")
        labels = {"tipo": "¿Qué está mal?", "valor_sugerido": "Valor correcto",
                  "comentario": "Comentario (opcional)"}
        help_texts = {"valor_sugerido": "Para la cantidad escribe los gramos; para el método, por ejemplo «asado»; "
                                        "para el componente, el nombre correcto."}
        widgets = {"comentario": forms.Textarea(attrs={"rows": 2})}


# --- Peso y metas (RF8, RF9) ------------------------------------------------------------


class PesajeForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Pesaje
        fields = ("fecha", "peso_kg", "observacion")
        widgets = {"fecha": FECHA}
        labels = {"peso_kg": "Peso (kg)", "observacion": "Observación (opcional)"}

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)

    def clean_fecha(self):
        fecha = self.cleaned_data["fecha"]
        if fecha > timezone.localdate():
            raise forms.ValidationError("No se pueden registrar pesajes futuros.")
        repetido = Pesaje.objects.filter(usuario=self.usuario, fecha=fecha).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise forms.ValidationError("Ya registraste un pesaje ese día; puedes editarlo.")
        return fecha


class AjusteManualForm(EstiloMixin, forms.Form):
    kcal = forms.DecimalField(label="Meta diaria que propones (kcal)", min_value=Decimal("800"),
                              max_value=Decimal("6000"), decimal_places=0)


# --- Alimentos personales y calculadora (RF3, RF15) --------------------------------------


class AlimentoPersonalForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Alimento
        fields = ("nombre", "categoria", "estado_fisico", "kcal", "proteinas", "carbohidratos", "azucares", "grasas",
                  "grasas_saturadas", "fibra", "sodio_mg", "densidad", "fuente_detalle")
        labels = {"kcal": "Energía (kcal por 100 g)", "fuente_detalle": "¿De dónde salen los datos?"}
        help_texts = {"fuente_detalle": "Por ejemplo: «etiqueta del paquete»."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"] = forms.ChoiceField(
            choices=[(c, c) for c in parametro("categorias_alimento")], label="Categoría",
            widget=forms.Select(attrs={"class": "campo"}),
        )


class CalculadoraAceiteForm(EstiloMixin, forms.Form):
    alimento = forms.ModelChoiceField(
        queryset=Alimento.objects.filter(ambito="global", estado="activo").exclude(matriz="otro").order_by("nombre"),
        label="Alimento que se fríe",
    )
    peso_crudo_g = forms.DecimalField(label="Peso en crudo (g)", min_value=Decimal("1"), max_value=Decimal("3000"),
                                      initial=Decimal("100"))
    metodo = forms.ModelChoiceField(queryset=MetodoCoccion.objects.filter(es_fritura=True, estado="activo"),
                                    label="Tipo de fritura")
    tamano = forms.ChoiceField(choices=[("", "Normal"), ("pequena", "Pieza pequeña"), ("mediana", "Pieza mediana"),
                                        ("grande", "Pieza grande")], required=False, label="Tamaño de la pieza")
    tiempo = forms.ChoiceField(choices=[("", "Normal"), ("corto", "Corto"), ("largo", "Largo, bien tostado")],
                               required=False, label="Tiempo de fritura")
    escurrido = forms.BooleanField(required=False, label="Se escurrió sobre papel absorbente")
    aceite_agregado_g = forms.DecimalField(required=False, min_value=Decimal("0.1"), max_value=Decimal("200"),
                                           label="Aceite agregado a la sartén (g, solo sartén)")


# --- Curación (RF3–RF6, RF19) --------------------------------------------------------------


class AlimentoCatalogoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Alimento
        fields = ("nombre", "categoria", "estado_fisico", "kcal", "proteinas", "carbohidratos", "azucares", "grasas",
                  "grasas_saturadas", "fibra", "sodio_mg", "agua_pct", "densidad", "rendimiento_pct",
                  "grasa_visible_pct", "matriz", "metodo_defecto", "fuente", "fuente_detalle", "verificado", "estado")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"] = forms.ChoiceField(
            choices=[(c, c) for c in parametro("categorias_alimento")], label="Categoría",
            widget=forms.Select(attrs={"class": "campo"}),
        )


class PreparacionForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Preparacion
        fields = ("nombre", "descripcion", "region", "categoria", "peso_porcion_g", "metodo_defecto",
                  "admite_variantes", "verificada", "estado")
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 2})}


class ComponenteForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Componente
        fields = ("alimento", "cantidad_g", "metodo", "rol", "opcional")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["alimento"].queryset = Alimento.objects.filter(ambito="global", estado="activo")


ComponentesFormSet = inlineformset_factory(Preparacion, Componente, form=ComponenteForm, extra=2, can_delete=True)


class MetodoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = MetodoCoccion
        fields = ("nombre", "usa_grasa", "es_fritura", "factor_agua", "perdida_grasa", "palabras", "estado")
        widgets = {"palabras": forms.Textarea(attrs={"rows": 2})}


class CoeficienteForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = CoeficienteAbsorcion
        fields = ("metodo", "matriz", "pct_min", "pct_tipico", "pct_max", "fuente", "estado")


class TerminoForm(EstiloMixin, forms.ModelForm):
    destino_texto = forms.CharField(label="Apunta a", max_length=120,
                                    widget=forms.TextInput(attrs={"list": "destinos", "autocomplete": "off"}),
                                    help_text="Nombre exacto de un alimento, una preparación o un método de cocción.")

    class Meta:
        model = TerminoLexico
        fields = ("termino", "region", "estado")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.destino:
            self.fields["destino_texto"].initial = self.instance.destino.nombre

    def clean(self):
        from core.services.catalogo import buscar_por_nombre

        datos = super().clean()
        texto = datos.get("destino_texto", "")
        destino = buscar_por_nombre(texto) or MetodoCoccion.objects.filter(nombre__iexact=texto.strip()).first()
        if destino is None:
            self.add_error("destino_texto", "No existe ningún alimento, preparación o método con ese nombre.")
            return datos
        self.instance.alimento = destino if isinstance(destino, Alimento) else None
        self.instance.preparacion = destino if isinstance(destino, Preparacion) else None
        self.instance.metodo = destino if isinstance(destino, MetodoCoccion) else None
        self.instance.tipo = ("alimento" if isinstance(destino, Alimento)
                              else "preparacion" if isinstance(destino, Preparacion) else "metodo")
        termino = normalizar(datos.get("termino", ""))
        repetido = TerminoLexico.objects.filter(termino=termino).exclude(pk=self.instance.pk).first()
        if repetido:
            self.add_error("termino", f"Ese término ya existe y apunta a «{repetido.destino}».")
        datos["termino"] = termino
        return datos


class PorcionForm(EstiloMixin, forms.ModelForm):
    destino_texto = forms.CharField(label="Alimento o preparación", max_length=120,
                                    widget=forms.TextInput(attrs={"list": "destinos", "autocomplete": "off"}))

    class Meta:
        model = PorcionCasera
        fields = ("medida", "cantidad", "por_defecto")

    def clean(self):
        from core.services.catalogo import buscar_por_nombre

        datos = super().clean()
        destino = buscar_por_nombre(datos.get("destino_texto", ""))
        if destino is None:
            self.add_error("destino_texto", "No existe ese alimento o preparación.")
            return datos
        self.instance.alimento = destino if isinstance(destino, Alimento) else None
        self.instance.preparacion = destino if isinstance(destino, Preparacion) else None
        return datos


class ResolverTerminoForm(EstiloMixin, forms.Form):
    destino = forms.CharField(label="Corresponde a", max_length=120,
                              widget=forms.TextInput(attrs={"list": "destinos", "autocomplete": "off"}))

    def clean_destino(self):
        from core.services.catalogo import buscar_por_nombre

        texto = self.cleaned_data["destino"]
        destino = buscar_por_nombre(texto) or MetodoCoccion.objects.filter(nombre__iexact=texto.strip()).first()
        if destino is None:
            raise forms.ValidationError("Elige un alimento, preparación o método existente (o créalo primero).")
        return destino


class RevisarCorreccionForm(EstiloMixin, forms.Form):
    decision = forms.ChoiceField(choices=[("aceptar", "Aceptar"), ("rechazar", "Rechazar")], widget=forms.RadioSelect)
    resolucion = forms.CharField(label="Respuesta para el usuario", widget=forms.Textarea(attrs={"rows": 2}),
                                 required=False)


class FraseReferenciaForm(EstiloMixin, forms.ModelForm):
    componentes = forms.CharField(
        label="Componentes esperados", widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Uno por línea: nombre exacto del catálogo y, si importa, «|clave del método». "
                  "Ejemplo: Arepa de maíz|fritura_profunda",
    )

    class Meta:
        model = FraseReferencia
        fields = ("texto", "kcal_referencia", "validada", "activa")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["componentes"].initial = "\n".join(
                f"{c['nombre']}|{c['metodo']}" if c.get("metodo") else c["nombre"]
                for c in self.instance.componentes_esperados
            )

    def clean_componentes(self):
        from core.services.catalogo import buscar_por_nombre

        resultado = []
        for linea in self.cleaned_data["componentes"].splitlines():
            if not linea.strip():
                continue
            nombre, _, metodo = linea.partition("|")
            if buscar_por_nombre(nombre) is None:
                raise forms.ValidationError(f"«{nombre.strip()}» no está en el catálogo.")
            if metodo.strip() and not MetodoCoccion.objects.filter(clave=metodo.strip()).exists():
                raise forms.ValidationError(f"«{metodo.strip()}» no es una clave de método válida.")
            resultado.append({"nombre": nombre.strip(), "metodo": metodo.strip()})
        if not resultado:
            raise forms.ValidationError("Indica al menos un componente.")
        return resultado

    def save(self, commit=True):
        self.instance.componentes_esperados = self.cleaned_data["componentes"]
        return super().save(commit)


# --- Administración (RF1, RF11) --------------------------------------------------------------


class ParametroForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Parametro
        fields = ("valor",)
        widgets = {"valor": forms.Textarea(attrs={"rows": 3})}

    def clean_valor(self):
        valor = self.cleaned_data["valor"].strip()
        try:
            validar_valor(self.instance.tipo, valor)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return valor


class CuentaInternaForm(EstiloMixin, forms.Form):
    correo = forms.EmailField()
    nombres = forms.CharField(max_length=150)
    apellidos = forms.CharField(max_length=150)
    rol = forms.ChoiceField(choices=[(Rol.CURADOR, "Curador nutricional"), (Rol.ADMINISTRADOR, "Administrador")])
    password = forms.CharField(label="Contraseña inicial", widget=forms.PasswordInput, strip=False)

    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().lower()
        if get_user_model().objects.filter(username=correo).exists():
            raise forms.ValidationError("Ya existe una cuenta con ese correo.")
        return correo

    def clean_password(self):
        password = self.cleaned_data["password"]
        password_validation.validate_password(password)
        return password


class CambiarEstadoCuentaForm(forms.Form):
    estado = forms.ChoiceField(choices=[("activo", "Activar"), ("inactivo", "Desactivar"), ("bloqueado", "Bloquear")])


def cuenta_rol(usuario) -> str | None:
    cuenta = Cuenta.objects.filter(usuario=usuario).first()
    return cuenta.rol if cuenta else None
