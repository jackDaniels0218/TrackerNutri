"""
Modelos de NutriRegional, organizados por grupo de funciones del SRS.

    cuentas.py   RF1 Usuarios, RF2 Perfil, consentimientos, recordatorios
    catalogo.py  RF3 Alimentos, RF4 Preparaciones, RF5 Cocción, RF6 Léxico
    comidas.py   RF7 Comidas, RF10 Correcciones, días completos
    metas.py     RF8 Metas, RF9 Peso
    sistema.py   RF11 Parámetros, RF20 Notificaciones, RF21 Uso de IA,
                 RF22 Bitácora, RF19 Conjunto de prueba de exactitud

Se reexportan aquí para poder escribir `from core.models import Alimento`.
"""

from core.models.catalogo import (  # noqa: F401
    Alimento,
    Ambito,
    CategoriaPreparacion,
    CoeficienteAbsorcion,
    Componente,
    EstadoFisico,
    EstadoRegistro,
    FuenteDato,
    HistorialCatalogo,
    Matriz,
    MetodoCoccion,
    PorcionCasera,
    Preparacion,
    RolComponente,
    TerminoLexico,
    TerminoPendiente,
    TipoTermino,
    VersionCatalogo,
)
from core.models.comidas import (  # noqa: F401
    ESTADOS_QUE_CUENTAN,
    Comida,
    Correccion,
    DiaRegistro,
    EstadoComida,
    ItemComida,
    MotorInterpretacion,
    OrigenComida,
    OrigenDato,
    TipoComida,
)
from core.models.cuentas import (  # noqa: F401
    Consentimiento,
    Cuenta,
    EstadoCuenta,
    NivelActividad,
    Objetivo,
    PerfilNutricional,
    RecordatorioUsuario,
    Ritmo,
    Rol,
    Sexo,
    TipoConsentimiento,
)
from core.models.metas import MetaCalorica, OrigenMeta, Pesaje  # noqa: F401
from core.models.sistema import (  # noqa: F401
    Bitacora,
    CacheInterpretacion,
    EjecucionExactitud,
    FraseReferencia,
    Notificacion,
    Parametro,
    UsoIA,
)
