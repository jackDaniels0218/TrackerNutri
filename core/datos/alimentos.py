"""
Catálogo inicial de alimentos base (RF3, objetivo específico 3).

AVISO IMPORTANTE
----------------
Son ESTIMACIONES DE REFERENCIA reunidas para el prototipo con el orden de
magnitud de la TCAC (ICBF) y de USDA FoodData Central. NO son cifras
oficiales: todas se cargan con verificado=False hasta que el nutricionista
asesor las valide contra la fuente, como exige el SRS.

Valores por 100 g de parte comestible. Los nutrientes desconocidos se dejan
en None (nunca en cero).

Formato de cada fila:
    nombre, categoría, estado ("crudo" | "cocido"),
    kcal, proteínas, carbohidratos, grasas,
    y opcionales: azucares, grasas_saturadas, fibra, sodio_mg, agua_pct,
    matriz, metodo (clave del método por defecto), densidad, rendimiento,
    grasa_visible, fuente ("usda" | "tcac" | "etiqueta" | "estimado")
"""

CEREALES = "Cereales y derivados"
TUBERCULOS = "Tubérculos y plátanos"
LEGUMINOSAS = "Leguminosas"
CARNES = "Carnes"
EMBUTIDOS = "Embutidos"
PESCADOS = "Pescados"
HUEVOS = "Huevos"
LACTEOS = "Lácteos"
FRUTAS = "Frutas"
VERDURAS = "Verduras"
GRASAS = "Grasas y aceites"
DULCES = "Azúcares y dulces"
BEBIDAS = "Bebidas"
PANADERIA = "Productos de panadería"
CONDIMENTOS = "Condimentos"


def A(nombre, categoria, estado, kcal, prot, carb, grasa, **extra):
    return {
        "nombre": nombre,
        "categoria": categoria,
        "estado_fisico": estado,
        "kcal": kcal,
        "proteinas": prot,
        "carbohidratos": carb,
        "grasas": grasa,
        **extra,
    }


ALIMENTOS = [
    # --- Cereales y derivados ------------------------------------------------
    A("Harina de maíz precocida blanca", CEREALES, "crudo", 350, 7.0, 77.0, 1.5, azucares=0.6, fibra=5.0, sodio_mg=5, agua_pct=11, matriz="masa_maiz", fuente="tcac"),
    A("Maíz tierno (choclo)", CEREALES, "crudo", 86, 3.3, 19.0, 1.4, azucares=6.3, fibra=2.0, sodio_mg=15, agua_pct=76, metodo="hervido", fuente="usda"),
    A("Maíz peto cocido", CEREALES, "cocido", 120, 3.0, 25.0, 1.0, fibra=3.0, agua_pct=70, fuente="estimado"),
    A("Arroz blanco crudo", CEREALES, "crudo", 360, 6.6, 79.0, 0.6, fibra=1.0, sodio_mg=5, agua_pct=12, fuente="usda"),
    A("Arroz blanco cocido", CEREALES, "cocido", 130, 2.7, 28.2, 0.3, azucares=0.1, fibra=0.4, sodio_mg=1, agua_pct=68.5, fuente="usda"),
    A("Arroz integral cocido", CEREALES, "cocido", 123, 2.7, 25.6, 1.0, fibra=1.6, agua_pct=70, fuente="usda"),
    A("Pasta (espagueti) cocida", CEREALES, "cocido", 158, 5.8, 30.9, 0.9, azucares=0.6, fibra=1.8, sodio_mg=1, agua_pct=62, fuente="usda"),
    A("Fideos de trigo cocidos", CEREALES, "cocido", 138, 4.5, 25.0, 2.1, fibra=1.2, agua_pct=67, fuente="usda"),
    A("Avena en hojuelas", CEREALES, "crudo", 379, 13.2, 67.7, 6.5, azucares=1.0, grasas_saturadas=1.1, fibra=10.1, sodio_mg=6, agua_pct=9, metodo="hervido", fuente="usda"),
    A("Harina de trigo", CEREALES, "crudo", 364, 10.3, 76.0, 1.0, azucares=0.3, fibra=2.7, sodio_mg=2, agua_pct=12, matriz="masa_trigo", fuente="usda"),
    A("Fécula de maíz (maicena)", CEREALES, "crudo", 381, 0.3, 91.0, 0.1, fibra=0.9, agua_pct=8, fuente="usda"),
    A("Almidón de yuca", CEREALES, "crudo", 357, 0.2, 88.0, 0.1, agua_pct=11, matriz="masa_maiz", fuente="estimado"),
    A("Quinua cocida", CEREALES, "cocido", 120, 4.4, 21.3, 1.9, azucares=0.9, fibra=2.8, sodio_mg=7, agua_pct=72, fuente="usda"),
    A("Cereal de maíz en hojuelas", CEREALES, "cocido", 375, 7.0, 84.0, 0.9, azucares=9.0, fibra=3.0, sodio_mg=700, agua_pct=3, fuente="etiqueta"),
    # --- Panadería -----------------------------------------------------------
    A("Pan blanco tajado", PANADERIA, "cocido", 265, 9.0, 49.0, 3.2, azucares=5.0, fibra=2.7, sodio_mg=490, agua_pct=36, fuente="usda"),
    A("Pan de sal", PANADERIA, "cocido", 300, 8.5, 55.0, 5.0, azucares=6.0, sodio_mg=450, agua_pct=30, fuente="estimado"),
    A("Pan integral", PANADERIA, "cocido", 250, 12.0, 41.0, 3.5, azucares=6.0, fibra=7.0, sodio_mg=450, agua_pct=38, fuente="usda"),
    A("Galletas de soda", PANADERIA, "cocido", 420, 9.0, 71.0, 11.0, azucares=2.0, fibra=2.5, sodio_mg=950, agua_pct=4, fuente="etiqueta"),
    A("Calado (pan tostado)", PANADERIA, "cocido", 400, 11.0, 75.0, 6.0, azucares=8.0, sodio_mg=600, agua_pct=5, fuente="estimado"),
    A("Ponqué", PANADERIA, "cocido", 380, 5.0, 55.0, 16.0, azucares=30.0, grasas_saturadas=4.0, sodio_mg=300, agua_pct=22, fuente="estimado"),
    # --- Tubérculos y plátanos ----------------------------------------------
    A("Papa pastusa", TUBERCULOS, "crudo", 77, 2.0, 17.5, 0.1, azucares=0.8, fibra=2.2, sodio_mg=6, agua_pct=79, matriz="tuberculo", metodo="hervido", fuente="usda"),
    A("Papa criolla", TUBERCULOS, "crudo", 97, 2.4, 21.3, 0.2, fibra=1.8, agua_pct=75, matriz="tuberculo", metodo="hervido", fuente="tcac"),
    A("Yuca", TUBERCULOS, "crudo", 160, 1.4, 38.0, 0.3, azucares=1.7, fibra=1.8, sodio_mg=14, agua_pct=60, matriz="tuberculo", metodo="hervido", fuente="usda"),
    A("Plátano verde", TUBERCULOS, "crudo", 122, 1.3, 32.0, 0.4, azucares=8.0, fibra=2.3, sodio_mg=4, agua_pct=65, matriz="tuberculo", metodo="hervido", fuente="usda"),
    A("Plátano maduro", TUBERCULOS, "crudo", 122, 1.3, 32.0, 0.4, azucares=15.0, fibra=2.3, sodio_mg=4, agua_pct=65, matriz="tuberculo", metodo="horno", fuente="usda"),
    A("Ñame", TUBERCULOS, "crudo", 118, 1.5, 27.9, 0.2, azucares=0.5, fibra=4.1, agua_pct=70, matriz="tuberculo", metodo="hervido", fuente="usda"),
    A("Arracacha", TUBERCULOS, "crudo", 104, 1.0, 24.0, 0.2, fibra=2.0, agua_pct=74, matriz="tuberculo", metodo="hervido", fuente="tcac"),
    A("Batata", TUBERCULOS, "crudo", 86, 1.6, 20.1, 0.1, azucares=4.2, fibra=3.0, agua_pct=77, matriz="tuberculo", metodo="horno", fuente="usda"),
    # --- Leguminosas --------------------------------------------------------
    A("Fríjol rojo cocido", LEGUMINOSAS, "cocido", 127, 8.7, 22.8, 0.5, azucares=0.3, fibra=7.4, sodio_mg=1, agua_pct=67, fuente="usda"),
    A("Fríjol rojo seco", LEGUMINOSAS, "crudo", 333, 23.6, 60.0, 0.8, fibra=24.0, agua_pct=11, fuente="usda"),
    A("Lenteja cocida", LEGUMINOSAS, "cocido", 116, 9.0, 20.1, 0.4, azucares=1.8, fibra=7.9, sodio_mg=2, agua_pct=70, fuente="usda"),
    A("Garbanzo cocido", LEGUMINOSAS, "cocido", 164, 8.9, 27.4, 2.6, azucares=4.8, fibra=7.6, sodio_mg=7, agua_pct=60, fuente="usda"),
    A("Arveja seca cocida", LEGUMINOSAS, "cocido", 118, 8.3, 21.1, 0.4, fibra=8.3, agua_pct=69, fuente="usda"),
    A("Arveja verde", LEGUMINOSAS, "crudo", 81, 5.4, 14.5, 0.4, azucares=5.7, fibra=5.1, sodio_mg=5, agua_pct=79, metodo="hervido", fuente="usda"),
    A("Maní tostado", LEGUMINOSAS, "cocido", 585, 24.0, 21.0, 49.7, azucares=4.0, grasas_saturadas=6.9, fibra=8.0, sodio_mg=6, agua_pct=2, fuente="usda"),
    # --- Carnes --------------------------------------------------------------
    A("Carne de res, punta de anca", CARNES, "crudo", 190, 20.0, 0.0, 12.0, grasas_saturadas=5.0, sodio_mg=55, agua_pct=67, matriz="carne", metodo="asado", grasa_visible=10, fuente="estimado"),
    A("Carne de res, lomo fino", CARNES, "crudo", 143, 21.5, 0.0, 6.0, grasas_saturadas=2.4, sodio_mg=55, agua_pct=71, matriz="carne", metodo="asado", fuente="usda"),
    A("Carne de res, sobrebarriga", CARNES, "crudo", 230, 18.0, 0.0, 17.5, grasas_saturadas=7.0, sodio_mg=60, agua_pct=63, matriz="carne", metodo="horno", grasa_visible=15, fuente="estimado"),
    A("Carne de res, costilla", CARNES, "crudo", 290, 16.0, 0.0, 25.0, grasas_saturadas=10.0, sodio_mg=60, agua_pct=58, matriz="carne", metodo="asado", rendimiento=70, grasa_visible=15, fuente="usda"),
    A("Carne de res molida", CARNES, "crudo", 215, 18.5, 0.0, 15.5, grasas_saturadas=6.0, sodio_mg=70, agua_pct=65, matriz="carne", metodo="guisado", fuente="usda"),
    A("Carne de res, bola (para bistec)", CARNES, "crudo", 150, 21.0, 0.0, 7.0, grasas_saturadas=2.8, sodio_mg=55, agua_pct=71, matriz="carne", metodo="guisado", fuente="estimado"),
    A("Carne de res desmechada", CARNES, "cocido", 200, 30.0, 0.0, 9.0, grasas_saturadas=3.5, sodio_mg=60, agua_pct=60, fuente="estimado"),
    A("Hígado de res", CARNES, "crudo", 135, 20.4, 3.9, 3.6, grasas_saturadas=1.2, sodio_mg=69, agua_pct=71, matriz="carne", metodo="fritura_sarten", fuente="usda"),
    A("Lengua de res", CARNES, "crudo", 224, 14.9, 3.7, 16.1, grasas_saturadas=7.0, sodio_mg=69, agua_pct=64, matriz="carne", metodo="guisado", fuente="usda"),
    A("Pechuga de pollo sin piel", CARNES, "crudo", 120, 22.5, 0.0, 2.6, grasas_saturadas=0.6, sodio_mg=45, agua_pct=74, matriz="carne", metodo="plancha", fuente="usda"),
    A("Muslo de pollo con piel", CARNES, "crudo", 215, 17.0, 0.0, 16.0, grasas_saturadas=4.5, sodio_mg=80, agua_pct=66, matriz="carne", metodo="guisado", rendimiento=75, fuente="usda"),
    A("Pollo entero con piel", CARNES, "crudo", 215, 18.6, 0.0, 15.0, grasas_saturadas=4.3, sodio_mg=70, agua_pct=66, matriz="carne", metodo="asado", rendimiento=70, fuente="usda"),
    A("Pollo desmechado", CARNES, "cocido", 165, 31.0, 0.0, 3.6, grasas_saturadas=1.0, sodio_mg=74, agua_pct=65, fuente="usda"),
    A("Gallina", CARNES, "crudo", 230, 18.0, 0.0, 17.5, grasas_saturadas=5.0, sodio_mg=70, agua_pct=63, matriz="carne", metodo="hervido", rendimiento=65, fuente="estimado"),
    A("Carne de cerdo, lomo", CARNES, "crudo", 145, 21.0, 0.0, 6.5, grasas_saturadas=2.3, sodio_mg=50, agua_pct=72, matriz="carne", metodo="asado", fuente="usda"),
    A("Carne de cerdo, chuleta", CARNES, "crudo", 200, 19.0, 0.0, 13.5, grasas_saturadas=4.8, sodio_mg=55, agua_pct=67, matriz="carne", metodo="asado", rendimiento=80, fuente="usda"),
    A("Carne de cerdo, costilla", CARNES, "crudo", 280, 16.0, 0.0, 23.5, grasas_saturadas=8.5, sodio_mg=75, agua_pct=59, matriz="carne", metodo="asado", rendimiento=70, fuente="usda"),
    A("Carne de cerdo, pernil", CARNES, "crudo", 210, 18.0, 0.0, 15.0, grasas_saturadas=5.3, sodio_mg=60, agua_pct=66, matriz="carne", metodo="horno", fuente="usda"),
    A("Barriga de cerdo (tocino con cuero)", CARNES, "crudo", 520, 9.0, 0.0, 54.0, grasas_saturadas=19.0, sodio_mg=30, agua_pct=35, matriz="carne", metodo="fritura_propia_grasa", fuente="usda"),
    # --- Embutidos -----------------------------------------------------------
    A("Chorizo", EMBUTIDOS, "crudo", 300, 14.0, 2.0, 26.0, grasas_saturadas=9.5, sodio_mg=1000, agua_pct=54, matriz="carne", metodo="asado", fuente="estimado"),
    A("Morcilla", EMBUTIDOS, "cocido", 280, 10.0, 20.0, 18.0, grasas_saturadas=6.5, sodio_mg=700, agua_pct=50, fuente="estimado"),
    A("Salchicha", EMBUTIDOS, "cocido", 280, 11.0, 4.0, 24.5, azucares=1.0, grasas_saturadas=9.0, sodio_mg=950, agua_pct=57, fuente="etiqueta"),
    A("Jamón de cerdo", EMBUTIDOS, "cocido", 145, 17.0, 2.0, 7.5, grasas_saturadas=2.5, sodio_mg=1200, agua_pct=70, fuente="etiqueta"),
    A("Salchichón", EMBUTIDOS, "cocido", 330, 13.0, 4.0, 29.0, grasas_saturadas=10.0, sodio_mg=1300, agua_pct=50, fuente="estimado"),
    # --- Pescados ------------------------------------------------------------
    A("Mojarra (tilapia)", PESCADOS, "crudo", 96, 20.0, 0.0, 1.7, grasas_saturadas=0.6, sodio_mg=52, agua_pct=78, matriz="pescado", metodo="fritura_profunda", rendimiento=50, fuente="usda"),
    A("Bagre", PESCADOS, "crudo", 105, 16.5, 0.0, 4.3, grasas_saturadas=1.0, sodio_mg=43, agua_pct=79, matriz="pescado", metodo="guisado", fuente="usda"),
    A("Trucha", PESCADOS, "crudo", 140, 20.0, 0.0, 6.6, grasas_saturadas=1.4, sodio_mg=52, agua_pct=72, matriz="pescado", metodo="plancha", fuente="usda"),
    A("Bocachico", PESCADOS, "crudo", 115, 18.0, 0.0, 4.8, sodio_mg=50, agua_pct=76, matriz="pescado", metodo="fritura_profunda", rendimiento=55, fuente="tcac"),
    A("Salmón", PESCADOS, "crudo", 208, 20.0, 0.0, 13.4, grasas_saturadas=3.1, sodio_mg=59, agua_pct=64, matriz="pescado", metodo="plancha", fuente="usda"),
    A("Camarón", PESCADOS, "crudo", 85, 20.0, 0.9, 0.5, sodio_mg=120, agua_pct=79, matriz="pescado", metodo="plancha", fuente="usda"),
    A("Atún en lata en agua", PESCADOS, "cocido", 116, 25.5, 0.0, 1.0, sodio_mg=340, agua_pct=70, fuente="etiqueta"),
    A("Sardinas en salsa de tomate", PESCADOS, "cocido", 185, 17.0, 2.0, 12.0, grasas_saturadas=3.0, sodio_mg=400, agua_pct=66, fuente="etiqueta"),
    # --- Huevos --------------------------------------------------------------
    A("Huevo de gallina", HUEVOS, "crudo", 143, 12.6, 0.7, 9.5, azucares=0.4, grasas_saturadas=3.1, sodio_mg=142, agua_pct=76, matriz="huevo", metodo="hervido", fuente="usda"),
    A("Huevo de codorniz", HUEVOS, "crudo", 158, 13.0, 0.4, 11.0, grasas_saturadas=3.6, sodio_mg=141, agua_pct=74, matriz="huevo", metodo="hervido", fuente="usda"),
    # --- Lácteos ---------------------------------------------------------------
    A("Leche entera", LACTEOS, "cocido", 61, 3.2, 4.8, 3.3, azucares=4.8, grasas_saturadas=1.9, sodio_mg=43, agua_pct=88, densidad=1.03, fuente="usda"),
    A("Leche semidescremada", LACTEOS, "cocido", 46, 3.3, 4.8, 1.5, azucares=4.8, grasas_saturadas=0.9, sodio_mg=44, agua_pct=89, densidad=1.03, fuente="usda"),
    A("Leche descremada", LACTEOS, "cocido", 35, 3.4, 5.0, 0.1, azucares=5.0, sodio_mg=42, agua_pct=91, densidad=1.03, fuente="usda"),
    A("Leche en polvo entera", LACTEOS, "cocido", 496, 26.0, 38.0, 26.7, azucares=38.0, grasas_saturadas=16.7, sodio_mg=371, agua_pct=2.5, fuente="usda"),
    A("Queso campesino", LACTEOS, "cocido", 270, 18.0, 3.0, 21.0, azucares=1.0, grasas_saturadas=13.0, sodio_mg=600, agua_pct=52, fuente="estimado"),
    A("Queso costeño", LACTEOS, "cocido", 330, 20.0, 3.0, 26.5, grasas_saturadas=16.5, sodio_mg=1500, agua_pct=45, fuente="estimado"),
    A("Queso doble crema", LACTEOS, "cocido", 330, 22.0, 2.0, 26.0, grasas_saturadas=16.0, sodio_mg=550, agua_pct=46, fuente="estimado"),
    A("Cuajada", LACTEOS, "cocido", 160, 12.0, 4.0, 10.5, azucares=3.0, grasas_saturadas=6.5, sodio_mg=80, agua_pct=72, fuente="estimado"),
    A("Kumis", LACTEOS, "cocido", 90, 3.2, 13.0, 2.8, azucares=12.0, grasas_saturadas=1.8, sodio_mg=45, agua_pct=80, densidad=1.04, fuente="etiqueta"),
    A("Yogur natural entero", LACTEOS, "cocido", 61, 3.5, 4.7, 3.3, azucares=4.7, grasas_saturadas=2.1, sodio_mg=46, agua_pct=88, densidad=1.03, fuente="usda"),
    A("Yogur con fruta", LACTEOS, "cocido", 95, 3.0, 16.0, 2.0, azucares=15.0, grasas_saturadas=1.3, sodio_mg=50, agua_pct=78, densidad=1.05, fuente="etiqueta"),
    A("Mantequilla", GRASAS, "cocido", 717, 0.9, 0.1, 81.0, grasas_saturadas=51.0, sodio_mg=11, agua_pct=16, fuente="usda"),
    A("Crema de leche", LACTEOS, "cocido", 340, 2.1, 2.8, 36.0, azucares=2.8, grasas_saturadas=23.0, sodio_mg=38, agua_pct=58, fuente="usda"),
    A("Arequipe", DULCES, "cocido", 315, 6.8, 55.0, 7.4, azucares=50.0, grasas_saturadas=4.6, sodio_mg=129, agua_pct=29, fuente="estimado"),
    # --- Frutas ----------------------------------------------------------------
    A("Banano", FRUTAS, "crudo", 89, 1.1, 22.8, 0.3, azucares=12.2, fibra=2.6, sodio_mg=1, agua_pct=75, metodo="crudo", fuente="usda"),
    A("Manzana", FRUTAS, "crudo", 52, 0.3, 13.8, 0.2, azucares=10.4, fibra=2.4, sodio_mg=1, agua_pct=86, metodo="crudo", fuente="usda"),
    A("Pera", FRUTAS, "crudo", 57, 0.4, 15.2, 0.1, azucares=9.8, fibra=3.1, sodio_mg=1, agua_pct=84, metodo="crudo", fuente="usda"),
    A("Naranja", FRUTAS, "crudo", 47, 0.9, 11.8, 0.1, azucares=9.4, fibra=2.4, agua_pct=87, metodo="crudo", fuente="usda"),
    A("Mandarina", FRUTAS, "crudo", 53, 0.8, 13.3, 0.3, azucares=10.6, fibra=1.8, sodio_mg=2, agua_pct=85, metodo="crudo", fuente="usda"),
    A("Limón", FRUTAS, "crudo", 29, 1.1, 6.5, 0.3, azucares=2.5, fibra=2.8, sodio_mg=2, agua_pct=89, metodo="crudo", fuente="usda"),
    A("Papaya", FRUTAS, "crudo", 43, 0.5, 10.8, 0.3, azucares=7.8, fibra=1.7, sodio_mg=8, agua_pct=88, metodo="crudo", fuente="usda"),
    A("Mango", FRUTAS, "crudo", 60, 0.8, 15.0, 0.4, azucares=13.7, fibra=1.6, sodio_mg=1, agua_pct=84, metodo="crudo", fuente="usda"),
    A("Piña", FRUTAS, "crudo", 50, 0.5, 13.1, 0.1, azucares=9.9, fibra=1.4, sodio_mg=1, agua_pct=86, metodo="crudo", fuente="usda"),
    A("Guayaba", FRUTAS, "crudo", 68, 2.6, 14.3, 1.0, azucares=8.9, fibra=5.4, sodio_mg=2, agua_pct=81, metodo="crudo", fuente="usda"),
    A("Lulo", FRUTAS, "crudo", 28, 0.6, 6.5, 0.2, azucares=3.0, fibra=1.1, agua_pct=92, metodo="crudo", fuente="tcac"),
    A("Mora de Castilla", FRUTAS, "crudo", 43, 1.4, 9.6, 0.5, azucares=4.9, fibra=5.3, sodio_mg=1, agua_pct=88, metodo="crudo", fuente="usda"),
    A("Maracuyá", FRUTAS, "crudo", 97, 2.2, 23.4, 0.7, azucares=11.2, fibra=10.4, sodio_mg=28, agua_pct=73, metodo="crudo", fuente="usda"),
    A("Granadilla", FRUTAS, "crudo", 97, 2.4, 23.0, 0.7, azucares=11.0, fibra=10.0, agua_pct=73, metodo="crudo", fuente="tcac"),
    A("Fresa", FRUTAS, "crudo", 32, 0.7, 7.7, 0.3, azucares=4.9, fibra=2.0, sodio_mg=1, agua_pct=91, metodo="crudo", fuente="usda"),
    A("Patilla (sandía)", FRUTAS, "crudo", 30, 0.6, 7.6, 0.2, azucares=6.2, fibra=0.4, sodio_mg=1, agua_pct=91, metodo="crudo", fuente="usda"),
    A("Melón", FRUTAS, "crudo", 34, 0.8, 8.2, 0.2, azucares=7.9, fibra=0.9, sodio_mg=16, agua_pct=90, metodo="crudo", fuente="usda"),
    A("Uva", FRUTAS, "crudo", 69, 0.7, 18.1, 0.2, azucares=15.5, fibra=0.9, sodio_mg=2, agua_pct=81, metodo="crudo", fuente="usda"),
    A("Aguacate", FRUTAS, "crudo", 160, 2.0, 8.5, 14.7, azucares=0.7, grasas_saturadas=2.1, fibra=6.7, sodio_mg=7, agua_pct=73, metodo="crudo", fuente="usda"),
    A("Tomate de árbol", FRUTAS, "crudo", 40, 1.8, 8.5, 0.4, azucares=4.0, fibra=3.3, agua_pct=86, metodo="crudo", fuente="tcac"),
    A("Guanábana", FRUTAS, "crudo", 66, 1.0, 16.8, 0.3, azucares=13.5, fibra=3.3, sodio_mg=14, agua_pct=81, metodo="crudo", fuente="usda"),
    A("Feijoa", FRUTAS, "crudo", 55, 1.0, 13.0, 0.6, azucares=8.2, fibra=6.4, sodio_mg=3, agua_pct=83, metodo="crudo", fuente="usda"),
    A("Uchuva", FRUTAS, "crudo", 53, 1.9, 11.2, 0.7, fibra=4.9, agua_pct=85, metodo="crudo", fuente="usda"),
    A("Coco (pulpa)", FRUTAS, "crudo", 354, 3.3, 15.2, 33.5, azucares=6.2, grasas_saturadas=29.7, fibra=9.0, sodio_mg=20, agua_pct=47, metodo="crudo", fuente="usda"),
    # --- Verduras --------------------------------------------------------------
    A("Tomate", VERDURAS, "crudo", 18, 0.9, 3.9, 0.2, azucares=2.6, fibra=1.2, sodio_mg=5, agua_pct=94, metodo="crudo", fuente="usda"),
    A("Cebolla cabezona", VERDURAS, "crudo", 40, 1.1, 9.3, 0.1, azucares=4.2, fibra=1.7, sodio_mg=4, agua_pct=89, metodo="crudo", fuente="usda"),
    A("Cebolla larga", VERDURAS, "crudo", 32, 1.8, 7.3, 0.2, azucares=2.3, fibra=2.6, sodio_mg=16, agua_pct=90, metodo="crudo", fuente="usda"),
    A("Zanahoria", VERDURAS, "crudo", 41, 0.9, 9.6, 0.2, azucares=4.7, fibra=2.8, sodio_mg=69, agua_pct=88, metodo="hervido", fuente="usda"),
    A("Ahuyama", VERDURAS, "crudo", 26, 1.0, 6.5, 0.1, azucares=2.8, fibra=0.5, sodio_mg=1, agua_pct=92, metodo="hervido", fuente="usda"),
    A("Habichuela", VERDURAS, "crudo", 31, 1.8, 7.0, 0.2, azucares=3.3, fibra=2.7, sodio_mg=6, agua_pct=90, metodo="hervido", fuente="usda"),
    A("Lechuga", VERDURAS, "crudo", 15, 1.4, 2.9, 0.2, azucares=0.8, fibra=1.3, sodio_mg=28, agua_pct=95, metodo="crudo", fuente="usda"),
    A("Repollo", VERDURAS, "crudo", 25, 1.3, 5.8, 0.1, azucares=3.2, fibra=2.5, sodio_mg=18, agua_pct=92, metodo="crudo", fuente="usda"),
    A("Pepino", VERDURAS, "crudo", 15, 0.7, 3.6, 0.1, azucares=1.7, fibra=0.5, sodio_mg=2, agua_pct=95, metodo="crudo", fuente="usda"),
    A("Pimentón", VERDURAS, "crudo", 26, 1.0, 6.0, 0.3, azucares=4.2, fibra=2.1, sodio_mg=4, agua_pct=92, metodo="crudo", fuente="usda"),
    A("Brócoli", VERDURAS, "crudo", 34, 2.8, 5.0, 0.4, azucares=1.7, fibra=2.6, sodio_mg=33, agua_pct=89, metodo="vapor", fuente="usda"),
    A("Coliflor", VERDURAS, "crudo", 25, 1.9, 4.0, 0.3, azucares=1.9, fibra=2.0, sodio_mg=30, agua_pct=92, metodo="vapor", fuente="usda"),
    A("Espinaca", VERDURAS, "crudo", 23, 2.9, 2.0, 0.4, azucares=0.4, fibra=2.2, sodio_mg=79, agua_pct=91, metodo="crudo", fuente="usda"),
    A("Remolacha", VERDURAS, "crudo", 43, 1.6, 9.6, 0.2, azucares=6.8, fibra=2.8, sodio_mg=78, agua_pct=88, metodo="hervido", fuente="usda"),
    A("Champiñones", VERDURAS, "crudo", 22, 3.1, 2.0, 0.3, azucares=2.0, fibra=1.0, sodio_mg=5, agua_pct=92, metodo="fritura_sarten", fuente="usda"),
    A("Calabacín", VERDURAS, "crudo", 17, 1.2, 3.1, 0.3, azucares=2.5, fibra=1.0, sodio_mg=8, agua_pct=95, metodo="hervido", fuente="usda"),
    A("Guascas", VERDURAS, "crudo", 34, 3.0, 5.5, 0.4, agua_pct=88, metodo="hervido", fuente="estimado"),
    A("Cilantro", VERDURAS, "crudo", 23, 2.1, 2.5, 0.5, azucares=0.9, fibra=2.8, sodio_mg=46, agua_pct=92, metodo="crudo", fuente="usda"),
    A("Ajo", CONDIMENTOS, "crudo", 149, 6.4, 33.0, 0.5, azucares=1.0, fibra=2.1, sodio_mg=17, agua_pct=59, metodo="crudo", fuente="usda"),
    # --- Grasas y aceites --------------------------------------------------------
    A("Aceite vegetal", GRASAS, "cocido", 884, 0.0, 0.0, 100.0, grasas_saturadas=14.0, sodio_mg=0, agua_pct=0, densidad=0.92, fuente="usda"),
    A("Manteca de cerdo", GRASAS, "cocido", 902, 0.0, 0.0, 100.0, grasas_saturadas=39.0, sodio_mg=0, agua_pct=0, fuente="usda"),
    A("Margarina", GRASAS, "cocido", 717, 0.2, 0.7, 80.0, grasas_saturadas=15.0, sodio_mg=700, agua_pct=16, fuente="usda"),
    A("Mayonesa", GRASAS, "cocido", 680, 1.0, 0.6, 75.0, grasas_saturadas=11.7, sodio_mg=635, agua_pct=21, fuente="usda"),
    # --- Azúcares y dulces -------------------------------------------------------
    A("Azúcar blanca", DULCES, "cocido", 387, 0.0, 100.0, 0.0, azucares=100.0, sodio_mg=1, agua_pct=0, fuente="usda"),
    A("Panela", DULCES, "cocido", 380, 0.4, 95.0, 0.1, azucares=85.0, sodio_mg=30, agua_pct=4, fuente="tcac"),
    A("Miel de abejas", DULCES, "cocido", 304, 0.3, 82.4, 0.0, azucares=82.1, sodio_mg=4, agua_pct=17, fuente="usda"),
    A("Bocadillo de guayaba", DULCES, "cocido", 300, 0.5, 74.0, 0.1, azucares=60.0, fibra=3.0, sodio_mg=5, agua_pct=25, fuente="estimado"),
    A("Chocolate de mesa", DULCES, "cocido", 450, 4.0, 70.0, 18.0, azucares=65.0, grasas_saturadas=11.0, fibra=4.0, sodio_mg=10, agua_pct=2, fuente="etiqueta"),
    A("Chocolatina de leche", DULCES, "cocido", 535, 7.6, 59.4, 29.7, azucares=51.5, grasas_saturadas=18.5, fibra=3.4, sodio_mg=79, agua_pct=1.5, fuente="usda"),
    A("Gelatina preparada", DULCES, "cocido", 62, 1.2, 14.2, 0.0, azucares=13.5, sodio_mg=46, agua_pct=84, fuente="usda"),
    # --- Bebidas -------------------------------------------------------------
    A("Agua", BEBIDAS, "cocido", 0, 0.0, 0.0, 0.0, azucares=0.0, sodio_mg=0, agua_pct=100, densidad=1.0, fuente="estimado"),
    A("Gaseosa azucarada (cola)", BEBIDAS, "cocido", 42, 0.0, 10.6, 0.0, azucares=10.6, sodio_mg=4, agua_pct=89, densidad=1.04, fuente="etiqueta"),
    A("Gaseosa azucarada de sabores", BEBIDAS, "cocido", 45, 0.0, 11.3, 0.0, azucares=11.3, sodio_mg=10, agua_pct=88, densidad=1.04, fuente="etiqueta"),
    A("Malta (bebida de malta)", BEBIDAS, "cocido", 63, 0.3, 15.5, 0.0, azucares=13.0, sodio_mg=15, agua_pct=84, densidad=1.04, fuente="etiqueta"),
    A("Café tinto (sin azúcar)", BEBIDAS, "cocido", 2, 0.1, 0.0, 0.0, azucares=0.0, sodio_mg=2, agua_pct=99, densidad=1.0, fuente="usda"),
    A("Té o aromática (sin azúcar)", BEBIDAS, "cocido", 1, 0.0, 0.2, 0.0, azucares=0.0, sodio_mg=1, agua_pct=99.7, densidad=1.0, fuente="usda"),
    A("Jugo de naranja natural", BEBIDAS, "cocido", 45, 0.7, 10.4, 0.2, azucares=8.4, sodio_mg=1, agua_pct=88, densidad=1.04, fuente="usda"),
    A("Jugo de caja (néctar)", BEBIDAS, "cocido", 52, 0.1, 13.0, 0.0, azucares=12.0, sodio_mg=10, agua_pct=86, densidad=1.05, fuente="etiqueta"),
    A("Bebida láctea achocolatada", BEBIDAS, "cocido", 75, 3.0, 11.0, 2.0, azucares=10.0, grasas_saturadas=1.3, sodio_mg=60, agua_pct=82, densidad=1.05, fuente="etiqueta"),
    A("Bebida hidratante", BEBIDAS, "cocido", 26, 0.0, 6.4, 0.0, azucares=6.0, sodio_mg=41, agua_pct=94, densidad=1.02, fuente="etiqueta"),
    A("Refresco en polvo preparado", BEBIDAS, "cocido", 40, 0.0, 10.0, 0.0, azucares=10.0, sodio_mg=10, agua_pct=90, densidad=1.03, fuente="etiqueta"),
    # --- Condimentos y salsas ------------------------------------------------
    A("Sal", CONDIMENTOS, "cocido", 0, 0.0, 0.0, 0.0, sodio_mg=38758, agua_pct=0, fuente="usda"),
    A("Salsa de tomate", CONDIMENTOS, "cocido", 112, 1.0, 27.0, 0.1, azucares=22.8, sodio_mg=900, agua_pct=69, fuente="usda"),
    A("Salsa rosada", CONDIMENTOS, "cocido", 400, 1.0, 10.0, 40.0, azucares=8.0, sodio_mg=700, agua_pct=47, fuente="estimado"),
    A("Ají casero", CONDIMENTOS, "cocido", 30, 1.0, 6.0, 0.3, azucares=3.0, sodio_mg=400, agua_pct=90, fuente="estimado"),
    A("Hogao comercial", CONDIMENTOS, "cocido", 90, 1.5, 9.0, 5.5, azucares=5.0, sodio_mg=500, agua_pct=82, fuente="etiqueta"),
]
