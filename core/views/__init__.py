"""
Vistas web de NutriRegional, separadas por rol y módulo del SRS:

    acceso.py          páginas públicas, registro en 3 pasos e ingreso
    comidas.py         Usuario: panel, texto libre, confirmación, manual, historial
    seguimiento.py     Usuario: peso, metas, reportes, calculadora de aceite
    cuenta.py          Usuario: perfil, privacidad, recordatorios, notificaciones
    curacion.py        Curador: catálogo, bandeja, versiones, exactitud
    administracion.py  Administrador: cuentas, parámetros, IA, auditoría, procesos

Las vistas no calculan: delegan en core/services/.
"""
