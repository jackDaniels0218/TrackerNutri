"""
Métodos de cocción y coeficientes de absorción de aceite (RF5).

AVISO: son valores de partida para el prototipo. El SRS exige que los valide
el nutricionista asesor con referencias antes de usarlos en producción.

factor_agua: % de cambio de peso al cocinar un alimento CRUDO.
    Los alimentos que ganan mucha agua al hervir (arroz, pasta, leguminosas)
    se registran ya cocidos en el catálogo, para no tener que modelar su
    absorción de agua con un único factor.
perdida_grasa: % de la grasa del alimento que se pierde (gotea) al cocinar.
"""

# clave, nombre, usa_grasa, es_fritura, factor_agua, perdida_grasa, palabras
METODOS = [
    ("fritura_profunda", "Fritura profunda", True, True, -20, 0,
     "frito, frita, fritos, fritas, fritico, fritica, apanado, apanada, apanados, apanadas, en aceite"),
    ("fritura_sarten", "Fritura en sartén con poco aceite", True, True, -15, 0,
     "en sarten, salteado, salteada, salteados, sellado, sellada, revuelto, revueltos, revuelta, al ajillo"),
    ("fritura_propia_grasa", "Fritura en su propia grasa", False, False, -40, 40,
     "en su propia grasa, chicharronado, chicharronada"),
    ("asado", "Asado a la parrilla", False, False, -30, 25,
     "asado, asada, asados, asadas, a la parrilla, a la brasa, al carbon, parrilla"),
    ("plancha", "A la plancha", False, False, -25, 15,
     "a la plancha, plancha, planchado"),
    ("horno", "Al horno", False, False, -25, 10,
     "al horno, horneado, horneada, horneados, horneadas, gratinado, gratinada"),
    ("guisado", "Guisado o sofrito", True, False, 0, 0,
     "guisado, guisada, guisados, sudado, sudada, en salsa, estofado, estofada, sofrito, desmechado, desmechada, encebollado, encebollada"),
    ("hervido", "Hervido", False, False, -10, 0,
     "hervido, hervida, hervidos, cocido, cocida, cocidos, cocidas, cosido, cosida, sancochado, sancochada, en caldo, en sopa"),
    ("vapor", "Al vapor", False, False, -5, 0, "al vapor, vapor"),
    ("crudo", "Crudo o sin cocción", False, False, 0, 0, "crudo, cruda, crudos, crudas"),
    ("mixto", "Preparación mixta", False, False, 0, 0,
     "preparacion mixta"),
]

FUENTE_COEFICIENTES = (
    "Valor de partida tomado de rangos publicados sobre absorción de aceite en "
    "fritura (Saguy y Dana, 2003; Ziaiifar et al., 2008). Pendiente de "
    "validación por el nutricionista asesor."
)

# método, matriz: (mínimo, típico, máximo) en % del peso crudo
COEFICIENTES = {
    ("fritura_profunda", "masa_maiz"): (8, 12, 18),
    ("fritura_profunda", "masa_trigo"): (10, 15, 22),
    ("fritura_profunda", "apanado"): (10, 15, 25),
    ("fritura_profunda", "tuberculo"): (5, 10, 15),
    ("fritura_profunda", "carne"): (2, 4, 8),
    ("fritura_profunda", "pescado"): (3, 6, 10),
    ("fritura_profunda", "huevo"): (6, 10, 15),
    ("fritura_profunda", "otro"): (4, 8, 12),
    ("fritura_sarten", "masa_maiz"): (3, 6, 10),
    ("fritura_sarten", "masa_trigo"): (4, 7, 12),
    ("fritura_sarten", "apanado"): (5, 9, 15),
    ("fritura_sarten", "tuberculo"): (3, 5, 9),
    ("fritura_sarten", "carne"): (1, 2, 5),
    ("fritura_sarten", "pescado"): (2, 4, 7),
    ("fritura_sarten", "huevo"): (4, 7, 12),
    ("fritura_sarten", "otro"): (2, 4, 8),
}
