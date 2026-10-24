"""
Conjunto inicial de frases de referencia para las pruebas de exactitud.

Cada frase indica qué componentes del catálogo deben identificarse y, cuando
importa, con qué método de cocción (clave del método).

AVISO: el SRS pide 200 frases validadas por un nutricionista. Este conjunto
lo escribió el equipo de desarrollo para el prototipo: sirve como prueba de
regresión (detecta si un cambio del catálogo o del motor empeora la
interpretación), no como medida de la exactitud real con usuarios. Se carga
con validada=False hasta que el nutricionista lo revise y lo amplíe.
"""


def F(texto, *componentes):
    esperados = []
    for c in componentes:
        nombre, _, metodo = c.partition("|")
        esperados.append({"nombre": nombre, "metodo": metodo})
    return {"texto": texto, "componentes": esperados}


FRASES = [
    # Las del enunciado
    F("Hoy almorcé una arepa frita mediana, aproximadamente 150 gramos de carne de res asada, una porción de arroz y una Coca-Cola de 400 ml",
      "Arepa de maíz|fritura_profunda", "Carne de res, punta de anca|asado", "Arroz blanco cocido", "Gaseosa azucarada (cola)"),
    F("Me comí una arepa frita con carne asada y una Coca-Cola",
      "Arepa de maíz|fritura_profunda", "Carne de res, punta de anca|asado", "Gaseosa azucarada (cola)"),
    F("Me comí una arepa frita mediana, dos huevos y una Coca-Cola de 400 ml",
      "Arepa de maíz|fritura_profunda", "Huevo de gallina", "Gaseosa azucarada (cola)"),
    # Desayunos
    F("desayuné dos huevos pericos, una arepa asada y un tinto", "Huevos pericos|fritura_sarten", "Arepa de maíz|asado", "Café tinto (sin azúcar)"),
    F("un tinto con dos cucharadas de azúcar", "Café tinto (sin azúcar)", "Azúcar blanca"),
    F("changua con calado", "Changua|hervido", "Calado (pan tostado)"),
    F("calentado paisa con huevo frito y arepa", "Calentado paisa|fritura_sarten", "Huevo de gallina|fritura_sarten", "Arepa de maíz|asado"),
    F("un chocolate con almojábana", "Chocolate en leche|hervido", "Almojábana|horno"),
    F("pandebono y un café con leche", "Pandebono|horno", "Café con leche|hervido"),
    F("dos huevos revueltos con pan", "Huevos revueltos|fritura_sarten", "Pan de sal"),
    F("arepa de choclo con quesito", "Arepa de choclo|plancha", "Queso campesino"),
    F("una arepa boyacense y aguapanela", "Arepa boyacense|plancha", "Aguapanela|hervido"),
    F("un buñuelo y una avena", "Buñuelo|fritura_profunda", "Avena colombiana|hervido"),
    F("un pandeyuca con kumis", "Pandeyuca|horno", "Kumis"),
    F("un caldo de costilla con arepa", "Caldo de costilla|hervido", "Arepa de maíz|asado"),
    F("huevo cocido y una tostada", "Huevo de gallina|hervido", "Calado (pan tostado)"),
    F("pan con mantequilla y chocolate", "Pan de sal", "Mantequilla", "Chocolate en leche|hervido"),
    F("una taza de cereal con leche", "Cereal de maíz en hojuelas", "Leche entera"),
    F("yogur con fresas", "Yogur con fruta", "Fresa"),
    F("un banano y un vaso de leche", "Banano", "Leche entera"),
    # Almuerzos
    F("una bandeja paisa", "Bandeja paisa|mixto"),
    F("almorcé bandeja paisa con jugo de mora", "Bandeja paisa|mixto", "Jugo de mora en leche|crudo"),
    F("un plato de ajiaco con aguacate", "Ajiaco santafereño|hervido", "Aguacate"),
    F("sancocho de gallina con arroz y aguacate", "Sancocho de gallina|hervido", "Arroz blanco cocido", "Aguacate"),
    F("arroz con pollo y una limonada", "Arroz con pollo|guisado", "Limonada|crudo"),
    F("frijoles con arroz, chicharrón y tajadas de maduro", "Fríjoles antioqueños|guisado", "Arroz blanco cocido",
      "Chicharrón|fritura_propia_grasa", "Tajadas de maduro|fritura_profunda"),
    F("lentejas con arroz y ensalada", "Lentejas guisadas|guisado", "Arroz blanco cocido", "Ensalada de tomate y cebolla|crudo"),
    F("sudado de pollo con papa y arroz", "Sudado de pollo|guisado", "Papa pastusa", "Arroz blanco cocido"),
    F("carne en bistec con arroz y papa", "Carne en bistec|guisado", "Arroz blanco cocido", "Papa pastusa"),
    F("sobrebarriga en salsa con papa criolla", "Sobrebarriga en salsa|guisado", "Papa criolla"),
    F("pescado frito con patacón y arroz de coco", "Mojarra frita|fritura_profunda", "Patacón|fritura_profunda", "Arroz de coco|guisado"),
    F("mojarra frita con ensalada", "Mojarra frita|fritura_profunda", "Ensalada de tomate y cebolla|crudo"),
    F("sudado de pescado con arroz", "Sudado de pescado|guisado", "Arroz blanco cocido"),
    F("mute santandereano", "Mute santandereano|hervido"),
    F("una sopa de verduras y un jugo de lulo", "Sopa de verduras|hervido", "Jugo de lulo en agua|crudo"),
    F("sopa de pasta con pan", "Sopa de pasta|hervido", "Pan de sal"),
    F("crema de ahuyama", "Crema de ahuyama|hervido"),
    F("pechuga a la plancha con ensalada", "Pechuga de pollo sin piel|plancha", "Ensalada de tomate y cebolla|crudo"),
    F("pollo asado con papas a la francesa", "Pollo asado|asado", "Papas a la francesa|fritura_profunda"),
    F("chuleta valluna con arroz", "Chuleta valluna|fritura_profunda", "Arroz blanco cocido"),
    F("lomo de cerdo asado con yuca", "Carne de cerdo, lomo|asado", "Yuca"),
    F("150 gramos de lomo fino a la plancha", "Carne de res, lomo fino|plancha"),
    F("carne molida guisada con arroz", "Carne de res molida|guisado", "Arroz blanco cocido"),
    F("hígado frito con arroz", "Hígado de res|fritura_profunda", "Arroz blanco cocido"),
    F("trucha a la plancha con papa salada", "Trucha|plancha", "Papa pastusa"),
    F("costilla de cerdo asada", "Carne de cerdo, costilla|asado"),
    F("un tamal con chocolate", "Tamal tolimense|hervido", "Chocolate en leche|hervido"),
    F("un plato de espaguetis", "Pasta (espagueti) cocida"),
    F("arroz, fríjol cocido y carne desmechada", "Arroz blanco cocido", "Fríjol rojo cocido", "Carne de res desmechada"),
    F("atún con arroz", "Atún en lata en agua", "Arroz blanco cocido"),
    # Comidas rápidas y fritos
    F("dos empanadas de carne con ají", "Empanada de carne|fritura_profunda", "Ají casero"),
    F("empanadas de pollo y una gaseosa", "Empanada de pollo|fritura_profunda", "Gaseosa azucarada (cola)"),
    F("tres patacones con hogao", "Patacón|fritura_profunda", "Hogao|guisado"),
    F("una papa rellena", "Papa rellena|fritura_profunda"),
    F("una carimañola", "Carimañola|fritura_profunda"),
    F("deditos de queso", "Deditos de queso|fritura_profunda"),
    F("un perro caliente y una colombiana", "Perro caliente|mixto", "Gaseosa azucarada de sabores"),
    F("papa criolla frita con chorizo", "Papa criolla frita|fritura_profunda", "Chorizo|asado"),
    F("yuca frita con guacamole", "Yuca frita|fritura_profunda", "Guacamole|crudo"),
    F("arepa de huevo", "Arepa de huevo|fritura_profunda"),
    F("chorizo con arepa", "Chorizo|asado", "Arepa de maíz|asado"),
    F("una morcilla y una pony malta", "Morcilla", "Malta (bebida de malta)"),
    F("salchicha con papas fritas", "Salchicha", "Papas a la francesa|fritura_profunda"),
    F("huevo frito con una cucharada de aceite", "Huevo de gallina|fritura_sarten"),
    F("maduro frito con queso", "Plátano maduro|fritura_profunda", "Queso campesino"),
    F("maduro asado con queso", "Plátano maduro asado con queso|horno"),
    # Bebidas
    F("una gaseosa de 400 ml", "Gaseosa azucarada (cola)"),
    F("un vaso de jugo de naranja", "Jugo de naranja natural"),
    F("una limonada natural", "Limonada|crudo"),
    F("un jugo de guayaba en agua", "Jugo de guayaba en agua|crudo"),
    F("un jugo de maracuyá", "Jugo de maracuyá en agua|crudo"),
    F("aguapanela con limón", "Aguapanela con limón|hervido"),
    F("una aromática", "Té o aromática (sin azúcar)"),
    F("un vaso de agua", "Agua"),
    F("una botella de bebida hidratante", "Bebida hidratante"),
    F("una leche achocolatada", "Bebida láctea achocolatada"),
    F("un jugo de caja", "Jugo de caja (néctar)"),
    F("una lata de gaseosa de manzana", "Gaseosa azucarada de sabores"),
    # Meriendas y postres
    F("un salpicón", "Salpicón|crudo"),
    F("natilla con buñuelo", "Natilla|hervido", "Buñuelo|fritura_profunda"),
    F("arroz con leche", "Arroz con leche|hervido"),
    F("una mazamorra con panela", "Mazamorra antioqueña|hervido", "Panela"),
    F("bocadillo con queso", "Bocadillo con queso|crudo"),
    F("cuajada con melao", "Cuajada con melao|crudo"),
    F("unas obleas con arequipe", "Obleas con arequipe|crudo"),
    F("una manzana y una mandarina", "Manzana", "Mandarina"),
    F("una tajada de papaya", "Papaya"),
    F("un mango", "Mango"),
    F("una chocolatina", "Chocolatina de leche"),
    F("un pedazo de ponqué", "Ponqué"),
    F("galletas de soda con queso", "Galletas de soda", "Queso campesino"),
    F("maní", "Maní tostado"),
    F("gelatina", "Gelatina preparada"),
    # Errores de ortografía y regionalismos
    F("chicarron con aripa", "Chicharrón|fritura_propia_grasa", "Arepa de maíz|asado"),
    F("frisoles con garra", "Fríjoles antioqueños|guisado"),
    F("un tintico", "Café tinto (sin azúcar)"),
    F("una pony malta y un pan", "Malta (bebida de malta)", "Pan de sal"),
    F("tostones con queso costeño", "Patacón|fritura_profunda", "Queso costeño"),
    F("una mogolla y un tinto", "Pan integral", "Café tinto (sin azúcar)"),
]
