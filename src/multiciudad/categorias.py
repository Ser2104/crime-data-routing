"""
Traduccion de las categorias de delito de cada ciudad a listas CERRADAS comunes
(investigacion/reglas_de_datos.md, secciones 2 y 3).

Cada delito recibe un codigo al estilo NIBRS (el estandar del FBI) y de ahi:
    clase_nucleo      homicidio | robo | agresion_grave | None   (lo que se califica)
    categoria_amplia  la definicion amplia de Pittsburgh | None (nivel B y medida secundaria)
    bolsa             violento | propiedad | otro                (nivel C)
Los delitos sexuales reciben el codigo SEXUAL y se excluyen en todas las ciudades.

Ciudades con codigos estandar: Pittsburgh y Seattle (NIBRS), Chicago (FBI code).
Ciudades con nombres propios: Gainesville y Chapel Hill (reglas por palabras,
en orden: gana la primera que coincide). Cincinnati solo publica categorias
gruesas (STARS): da el nucleo y las bolsas, pero no la categoria amplia.
"""
import re

CLASES_NUCLEO = ["homicidio", "robo", "agresion_grave"]
CATEGORIAS_AMPLIAS = ["homicidio", "robo", "agresion_grave", "agresion_simple", "amenaza", "armas",
                      "arrebato", "carterista", "secuestro", "drogas"]
BOLSAS = ["violento", "propiedad", "otro"]
SEXUAL = "SEXUAL"
PROPIEDAD = "PROP"           # propiedad sin codigo detallado
VIOLENTO_SIN_DETALLE = "VIOL"  # violento sin saber cual (Cincinnati "Part 1 Violent")

# Codigo NIBRS -> categoria amplia
AMPLIA = {"09A": "homicidio", "120": "robo", "13A": "agresion_grave", "13B": "agresion_simple",
          "13C": "amenaza", "520": "armas", "23B": "arrebato", "23A": "carterista", "100": "secuestro",
          "35A": "drogas", "35B": "drogas"}
NUCLEO = {"09A": "homicidio", "120": "robo", "13A": "agresion_grave"}
# Delitos contra la propiedad del FBI (Part I): robo en vivienda o local, hurtos, robo de vehiculo, incendio
CODIGOS_PROPIEDAD = {"200", "220", "23A", "23B", "23C", "23D", "23E", "23F", "23G", "23H", "240", PROPIEDAD}
CODIGOS_SEXUALES = {"11A", "11B", "11C", "11D", "36A", "36B"}


def clasificar(codigo):
    """Codigo -> (clase_nucleo, categoria_amplia, bolsa). Los sexuales no llegan aqui."""
    if codigo in NUCLEO or codigo == VIOLENTO_SIN_DETALLE:
        bolsa = "violento"
    elif codigo in CODIGOS_PROPIEDAD:
        bolsa = "propiedad"
    else:
        bolsa = "otro"
    return NUCLEO.get(codigo), AMPLIA.get(codigo), bolsa


# ---------------------------------------------------------------------------
# Chicago: codigo FBI (fbi_code) + tipo principal
CHICAGO_FBI = {"01A": "09A", "01B": "09B", "02": SEXUAL, "03": "120", "04A": "13A", "04B": "13A",
               "05": "220", "06": "23H", "07": "240", "09": "200", "10": "250", "11": "26A", "12": "270",
               "13": "280", "14": "290", "15": "520", "16": "40A", "18": "35A", "19": "39A", "20": "90F",
               "22": "90G", "24": "90C"}


def codigo_chicago(fbi, tipo):
    fbi, tipo = str(fbi).strip(), str(tipo).strip().upper()
    if fbi == "08A":
        return "13C" if tipo in ("INTIMIDATION", "STALKING") else "13B" if tipo == "ASSAULT" else "90Z"
    if fbi == "08B":
        return "13B"
    if fbi == "15" and tipo == "NON-CRIMINAL":
        return "90Z"
    if fbi == "17":
        return "26A" if tipo == "DECEPTIVE PRACTICE" else "90Z" if tipo == "OTHER OFFENSE" else SEXUAL
    if fbi == "26":
        return {"KIDNAPPING": "100", "STALKING": "13C", "INTIMIDATION": "13C",
                "NARCOTICS": "35A", "HUMAN TRAFFICKING": "64A"}.get(tipo, "90Z")
    return CHICAGO_FBI.get(fbi, "90Z")


def codigo_nibrs(codigo):
    """Pittsburgh y Seattle publican el codigo NIBRS."""
    codigo = str(codigo).strip().upper()
    return SEXUAL if codigo in CODIGOS_SEXUALES else codigo


# ---------------------------------------------------------------------------
# Reglas por palabras (en orden). None = no es un delito de las listas (va a "otro").
_SEXUAL = (r"SEX|RAPE|FONDL|INDECENT|LEWD|LASC|MOLEST|PREDATOR|SODOMY|INCEST|PEEPING", SEXUAL)
GAINESVILLE = [
    _SEXUAL,
    (r"TRAFFIC|JUSTIFIABLE|NON-REPORTING|FOUND|LOST", None),
    (r"^HOMICIDE$|MURDER", "09A"),
    (r"SUDDEN SNATCH|PURSE SNATCH", "23B"),
    (r"POCKET-?\s?PICK", "23A"),
    (r"ROBBERY|CARJACK", "120"),
    (r"AGGRAVATED|AGGRAVATED ASSUALT|\bAGG\b|STRANGULATION|BATTERY \(FELONY\)|FELONY BATTERY(?! REPEAT)"
     r"|DEADLY MISSILE|HOMICIDE \(ATTEMPTED\)", "13A"),
    (r"KIDNAP|ABDUCT|FALSE IMPRISONMENT", "100"),
    (r"THEFT|BURGLARY|STOLEN VEHICLE|ARSON|SHOPLIFT|LARCENY", PROPIEDAD),
    (r"WEAPON|FIREARM|DISCHARGE", "520"),
    (r"THREAT|STALK|INTIMIDAT", "13C"),
    (r"BATTERY|ASSAULT", "13B"),
    (r"PARAPHERNALIA|DRUG EQUIP", "35B"),
    (r"DRUG|NARCOT|COCAINE|MARIJUANA|CONTROLLED SUBST|TRAFFICKING IN", "35A"),
]
CHAPEL_HILL = [
    _SEXUAL,
    (r"NO ASSAULT|NO THREAT|NON-ASSAULTIVE|NON ASSAULTIVE|SUICID|HEARD|INVESTIGATION|INFORMATION|SNIFF"
     r"|ASSIST|WARNING|SEARCH|COMPLAINT|POSSIBLE|ALLEGED|FOUND|LOST|DISPOSAL|ASSESSMENT|TOY GUN|PICK UP"
     r"|EXTINGUISHER|HIT AND RUN|DEATH|NEGLECT", None),
    (r"ATTEMPTED (MURDER|HOMICIDE)", "13A"),
    (r"MURDER|HOMICIDE", "09A"),
    (r"PURSE SNATCH|SNATCH", "23B"),
    (r"POCKET ?PICK", "23A"),
    (r"ROBBERY|CARJACK", "120"),
    (r"AGGRAVAT|DEADLY WEAPON|\bA\.?W\.?D\b|SERIOUS INJURY|STRANGUL|POINTING (A )?(FIREARM|GUN)|W/ ?INJURY"
     r"|WITH INJURY|/W /INJURY|MAIM|SHOOTING INTO", "13A"),
    (r"KIDNAP|ABDUCT", "100"),
    (r"LARCENY|THEFT|SHOPLIFT|B&E|BREAKING|BURGL|STOLEN VEHICLE|ARSON", PROPIEDAD),
    (r"WEAPON|FIREARM|CCW|\bGUN|BRANDISH|DISCHARG", "520"),
    (r"THREAT|INTIMIDAT|STALK", "13C"),
    (r"ASSAULT|BATTERY|SPITTLE", "13B"),
    (r"PARAPHERNALIA", "35B"),
    (r"DRUG|NARCOT|MARIJUANA|COCAINE|FENTANYL|HEROIN|CONTROLLED|PWISD|METH", "35A"),
]
REGLAS = {"gainesville": GAINESVILLE, "chapel_hill": CHAPEL_HILL}


def codigo_por_nombre(ciudad, nombre):
    texto = re.sub(r"\s+", " ", str(nombre).upper()).strip()
    for patron, codigo in REGLAS[ciudad]:
        if re.search(patron, texto):
            return codigo
    return None


# ---------------------------------------------------------------------------
# Cincinnati: solo categorias gruesas (STARS)
CINCINNATI_STARS = {"Homicide": "09A", "Robbery": "120", "Agg Assault": "13A",
                    "Strangulation": "13A",   # el FBI cuenta la estrangulacion como agresion grave
                    "Rape": SEXUAL, "Part 1 Violent": VIOLENTO_SIN_DETALLE,
                    "Auto Theft": PROPIEDAD, "Theft from Auto": PROPIEDAD, "Personal/Other Theft": PROPIEDAD,
                    "Burglary/BE": PROPIEDAD, "Part 1 Property": PROPIEDAD, "Part 2": None}

# Ciudades que permiten la categoria amplia (nivel B y medida secundaria)
CON_DETALLE = {"pittsburgh", "chicago", "seattle", "gainesville", "chapel_hill"}


# ---------------------------------------------------------------------------
# CIUDADES DE EXAMEN. Escritas el 2026-10-05 ANTES de abrir la caja fuerte, solo con
# documentacion oficial (nunca con sus registros):
#   Filadelfia: codigo UCR del FBI redondeado a centenas (ucr_general; "UCR codes are
#     generalized", OpenDataPhilly) -> clases del Manual UCR del FBI (Part I y II).
#   Baton Rouge: codigo NIBRS (nibrs_code), igual que Pittsburgh y Seattle.
#   Tempe: descripcion libre (OffenseCustom; diccionario oficial de Tempe) -> reglas
#     GENERICAS por palabras, armadas con las de las ciudades de desarrollo.
FILADELFIA_UCR = {100: "09A", 200: SEXUAL, 300: "120", 400: "13A", 500: "220", 600: "23H", 700: "240",
                  800: "13B", 900: "200", 1000: "250", 1100: "26A", 1200: "270", 1300: "280", 1400: "290",
                  1500: "520", 1600: "40A", 1700: SEXUAL, 1800: "35A", 1900: "39A", 2000: "90F", 2100: "90D",
                  2200: "90G", 2300: "90E", 2400: "90C", 2500: "90B", 2600: "90Z"}


def codigo_filadelfia(ucr, texto):
    """UCR del FBI a centenas. En 100 (homicidio) solo cuenta el doloso: el texto
    distingue 'Criminal' de 'Gross Negligence' y 'Justifiable'."""
    try:
        centena = int(float(ucr)) // 100 * 100
    except (TypeError, ValueError):
        return None
    codigo = FILADELFIA_UCR.get(centena, "90Z")
    if codigo == "09A" and re.search(r"NEGLIG|JUSTIF", str(texto).upper()):
        return "09B"
    return codigo


GENERICO = [
    _SEXUAL,
    (r"NO ASSAULT|NO THREAT|NON-ASSAULTIVE|NON ASSAULTIVE|SUICID|HEARD|INVESTIGAT|INFORMATION|\bINFO\b|ASSIST"
     r"|WARNING|FOUND|LOST|DEATH|\bTRAFFIC\b|VEHICULAR|JUSTIFIABLE|NEGLIGEN|WELFARE|ALARM", None),
    (r"ATTEMPTED (MURDER|HOMICIDE)|HOMICIDE.{0,3}ATTEMPT", "13A"),
    (r"MURDER|HOMICIDE|MANSLAUGHTER", "09A"),
    (r"PURSE.?SNATCH|SUDDEN SNATCH", "23B"),
    (r"POCKET.?PICK", "23A"),
    (r"ROBBERY|CARJACK", "120"),
    (r"AGGRAVAT|\bAGG\b|DEADLY WEAPON|\bA\.?D\.?W\b|\bA\.?W\.?D\b|SERIOUS (BODILY )?INJURY|STRANGUL"
     r"|POINTING (A )?(FIREARM|GUN)|W/ ?INJURY|WITH INJURY|MAIM|SHOOTING INTO|DEADLY MISSILE"
     r"|BATTERY \(FELONY\)|FELONY BATTERY(?! REPEAT)", "13A"),
    (r"KIDNAP|ABDUCT|FALSE IMPRISONMENT", "100"),
    (r"LARCENY|THEFT|SHOPLIFT|B&E|BREAKING|BURGL|STOLEN VEHICLE|ARSON", PROPIEDAD),
    (r"WEAPON|FIREARM|CCW|\bGUN|BRANDISH|DISCHARG", "520"),
    (r"THREAT|INTIMIDAT|STALK", "13C"),
    (r"ASSAULT|BATTERY", "13B"),
    (r"PARAPHERNALIA|DRUG EQUIP", "35B"),
    (r"DRUG|NARCOT|MARIJUANA|COCAINE|FENTANYL|HEROIN|CONTROLLED SUBST|DANGEROUS DRUG|\bMETH|PWISD"
     r"|TRAFFICKING IN", "35A"),
]
REGLAS["generico"] = GENERICO
CON_DETALLE |= {"filadelfia", "baton_rouge", "tempe"}
