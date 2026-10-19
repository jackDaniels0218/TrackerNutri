"""
Formularios de la aplicación.

Aquí vive la validación de lo que escribe el usuario. Ningún dato llega a la
base de datos sin pasar por uno de estos formularios o por un serializador.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from core.models import (
    Alimento,
    MetodoPreparacion,
    PerfilNutricional,
    RegistroComida,
    Unidad,
)
from core.services.nutrition import CantidadInvalida, validar_cantidad


class RegistroUsuarioForm(UserCreationForm):
    """
    Alta de usuario. Reutiliza UserCreationForm de Django para no reinventar
    el manejo de contraseñas (hash, validadores de seguridad, confirmación).
    """

    email = forms.EmailField(
        required=False,
        label="Correo electrónico (opcional)",
        widget=forms.EmailInput(attrs={"class": "campo"}),
    )

    class Meta:
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nombre de usuario"
        for campo in self.fields.values():
            campo.widget.attrs.setdefault("class", "campo")


class PerfilForm(forms.ModelForm):
    """Edición del perfil y de la meta diaria de calorías."""

    class Meta:
        model = PerfilNutricional
        fields = ("edad", "peso_kg", "estatura_cm", "meta_calorias_diaria")
        widgets = {
            "edad": forms.NumberInput(attrs={"class": "campo", "min": 1, "max": 120}),
            "peso_kg": forms.NumberInput(
                attrs={"class": "campo", "step": "0.1", "min": "1"}
            ),
            "estatura_cm": forms.NumberInput(
                attrs={"class": "campo", "min": 50, "max": 250}
            ),
            "meta_calorias_diaria": forms.NumberInput(
                attrs={"class": "campo", "min": 800, "max": 6000, "step": 10}
            ),
        }

    def clean_meta_calorias_diaria(self):
        """La meta debe ser un número de calorías plausible, no cero."""
        meta = self.cleaned_data["meta_calorias_diaria"]
        if meta < 800 or meta > 6000:
            raise forms.ValidationError(
                "Indica una meta entre 800 y 6000 kcal. Si necesitas un valor "
                "fuera de ese rango, consúltalo con un profesional."
            )
        return meta


class AnalisisComidaForm(forms.Form):
    """Campo de texto libre que se envía al servicio de IA."""

    texto = forms.CharField(
        label="¿Qué comiste?",
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": "campo",
                "rows": 3,
                "placeholder": (
                    "Ej.: Hoy almorcé una arepa frita mediana, 150 gramos de "
                    "carne de res asada, una porción de arroz y una gaseosa "
                    "de 400 ml."
                ),
            }
        ),
    )
    fecha = forms.DateField(
        label="Fecha",
        widget=forms.DateInput(attrs={"type": "date", "class": "campo"}),
    )

    def clean_texto(self):
        texto = self.cleaned_data["texto"].strip()
        if len(texto) < 3:
            raise forms.ValidationError("Describe la comida con un poco más de detalle.")
        return texto


class ComidaManualForm(forms.ModelForm):
    """
    Cabecera de una comida registrada a mano.

    Es la alternativa que siempre funciona, incluso sin clave de IA.
    """

    class Meta:
        model = RegistroComida
        fields = ("descripcion", "fecha", "hora")
        labels = {"descripcion": "Nombre de la comida"}
        widgets = {
            "descripcion": forms.TextInput(
                attrs={"class": "campo", "placeholder": "Ej.: Almuerzo"}
            ),
            "fecha": forms.DateInput(attrs={"type": "date", "class": "campo"}),
            "hora": forms.TimeInput(attrs={"type": "time", "class": "campo"}),
        }


class DetalleComidaForm(forms.Form):
    """
    Una fila editable de la lista de alimentos.

    Se usa tanto para confirmar lo que detectó la IA como para el registro
    manual. `alimento` puede quedar vacío: en ese caso el detalle se guarda sin
    valores nutricionales y se marca como pendiente, nunca con ceros.
    """

    alimento = forms.ModelChoiceField(
        queryset=Alimento.objects.filter(activo=True),
        required=False,
        empty_label="— Sin coincidencia en el catálogo —",
        label="Alimento",
        widget=forms.Select(attrs={"class": "campo"}),
    )
    nombre_mostrado = forms.CharField(
        max_length=120,
        label="Nombre",
        widget=forms.TextInput(attrs={"class": "campo"}),
    )
    cantidad = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        label="Cantidad",
        widget=forms.NumberInput(attrs={"class": "campo", "step": "0.01", "min": "0.01"}),
    )
    unidad = forms.ChoiceField(
        choices=Unidad.choices,
        label="Unidad",
        widget=forms.Select(attrs={"class": "campo"}),
    )
    metodo_preparacion = forms.ChoiceField(
        choices=MetodoPreparacion.choices,
        required=False,
        initial=MetodoPreparacion.NO_ESPECIFICADA,
        label="Preparación",
        widget=forms.Select(attrs={"class": "campo"}),
    )

    def clean_cantidad(self):
        """Rechaza cantidades negativas o cero con el mismo criterio que el motor."""
        try:
            return validar_cantidad(self.cleaned_data["cantidad"])
        except CantidadInvalida as exc:
            raise forms.ValidationError(str(exc)) from exc


# Formset usado en la página de confirmación y en el registro manual.
DetalleComidaFormSet = forms.formset_factory(
    DetalleComidaForm, extra=0, can_delete=True, min_num=1, validate_min=True
)

DetalleComidaFormSetManual = forms.formset_factory(
    DetalleComidaForm, extra=1, can_delete=True, min_num=1, validate_min=True
)
