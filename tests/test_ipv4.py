"""Pruebas del módulo de cálculo.

``ipaddress`` se usa SOLO aquí, como referencia independiente para comparar.
"""

import ipaddress
import pathlib
import random
import re

import pytest

from calc import ipv4
from calc.ipv4 import (
    ErrorValidacion,
    calcular,
    clase_de,
    clasificar_uso,
    interpretar_cidr,
    interpretar_direccion_mascara,
    mascara_desde_prefijo,
    octetos_a_entero,
    prefijo_desde_mascara,
)
from calc.respuesta import formatear_miles, respuesta_cidr, respuesta_direccion_mascara

SEMILLA = 20262  # fija: la prueba aleatoria es reproducible
PARES_ALEATORIOS = 3000


def ip(texto):
    return octetos_a_entero([int(parte) for parte in texto.split(".")])


# ---------------------------------------------------------------------------
# El módulo no usa atajos
# ---------------------------------------------------------------------------

def test_calc_no_importa_ipaddress_ni_flask():
    for archivo in pathlib.Path(ipv4.__file__).parent.glob("*.py"):
        codigo = archivo.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import|from)\s+(ipaddress|flask)\b", codigo, re.M), archivo
        assert "is_private" not in codigo and "is_global" not in codigo, archivo


# ---------------------------------------------------------------------------
# Conversiones y máscara
# ---------------------------------------------------------------------------

def test_conversion_ida_y_vuelta():
    assert ip("192.168.1.100") == 0xC0A80164
    assert ipv4.decimal_punteado(0xC0A80164) == "192.168.1.100"
    assert ipv4.binario_punteado(0xC0A80164) == "11000000.10101000.00000001.01100100"
    assert ipv4.decimal_punteado(0) == "0.0.0.0"
    assert ipv4.decimal_punteado(0xFFFFFFFF) == "255.255.255.255"


@pytest.mark.parametrize("prefijo", range(33))
def test_mascara_desde_prefijo_y_vuelta(prefijo):
    referencia = int(ipaddress.IPv4Network("0.0.0.0/{}".format(prefijo)).netmask)
    assert mascara_desde_prefijo(prefijo) == referencia
    assert prefijo_desde_mascara(referencia) == prefijo


def test_mascaras_no_contiguas_se_rechazan():
    validas = {mascara_desde_prefijo(p) for p in range(33)}
    azar = random.Random(SEMILLA)
    candidatos = [azar.getrandbits(32) for _ in range(20000)]
    # Además: cada máscara válida con un bit cambiado (casi todas dejan de ser contiguas).
    candidatos += [m ^ (1 << bit) for m in validas for bit in range(32)]
    for valor in candidatos:
        assert (prefijo_desde_mascara(valor) is not None) == (valor in validas), hex(valor)


@pytest.mark.parametrize("mascara", ["255.0.255.0", "255.255.255.1", "0.255.255.255",
                                     "255.255.0.255", "128.0.0.1", "254.255.255.0"])
def test_ejemplos_de_mascaras_no_contiguas(mascara):
    assert prefijo_desde_mascara(ip(mascara)) is None


def test_formato_de_miles():
    assert formatear_miles(0) == "0"
    assert formatear_miles(256) == "256"
    assert formatear_miles(999) == "999"
    assert formatear_miles(1000) == "1.000"
    assert formatear_miles(1024) == "1.024"
    assert formatear_miles(65536) == "65.536"
    assert formatear_miles(16777216) == "16.777.216"
    assert formatear_miles(4294967296) == "4.294.967.296"


# ---------------------------------------------------------------------------
# Comparación aleatoria contra ipaddress (unicast, prefijos 1 a 30)
# ---------------------------------------------------------------------------

def _pares_unicast_aleatorios():
    azar = random.Random(SEMILLA)
    pares = []
    while len(pares) < PARES_ALEATORIOS:
        direccion = azar.randrange(1, 224 << 24)  # clases A, B y C, sin 0.0.0.0
        pares.append((direccion, azar.randint(1, 30)))
    return pares


def test_aleatorio_contra_ipaddress():
    for direccion, prefijo in _pares_unicast_aleatorios():
        texto_ip = str(ipaddress.IPv4Address(direccion))
        red = ipaddress.ip_network("{}/{}".format(texto_ip, prefijo), strict=False)
        datos = respuesta_cidr("{}/{}".format(texto_ip, prefijo))["datos"]
        contexto = "{}/{}".format(texto_ip, prefijo)
        assert datos["red"] == str(red.network_address), contexto
        assert datos["broadcast"] == str(red.broadcast_address), contexto
        assert datos["mascara"] == str(red.netmask), contexto
        assert datos["total"] == red.num_addresses, contexto
        assert datos["hosts"] == red.num_addresses - 2, contexto
        assert datos["primer_host"] == str(red.network_address + 1), contexto
        assert datos["ultimo_host"] == str(red.broadcast_address - 1), contexto


def test_aleatorio_formas_a_y_b_iguales():
    for direccion, prefijo in _pares_unicast_aleatorios()[:500]:
        texto_ip = str(ipaddress.IPv4Address(direccion))
        mascara = str(ipaddress.IPv4Network("0.0.0.0/{}".format(prefijo)).netmask)
        assert respuesta_direccion_mascara(texto_ip, mascara) == respuesta_cidr(
            "{}/{}".format(texto_ip, prefijo)
        )


# ---------------------------------------------------------------------------
# Clase tradicional
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("direccion,clase", [
    ("0.0.0.0", "A"), ("127.255.255.255", "A"),
    ("128.0.0.0", "B"), ("191.255.255.255", "B"),
    ("192.0.0.0", "C"), ("223.255.255.255", "C"),
    ("224.0.0.0", "D"), ("239.255.255.255", "D"),
    ("240.0.0.0", "E"), ("255.255.255.255", "E"),
])
def test_clase_en_los_limites(direccion, clase):
    assert clase_de(ip(direccion)) == clase


# ---------------------------------------------------------------------------
# Clasificación de uso
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("direccion", ["127.0.0.1", "169.254.1.1", "240.0.0.1"])
def test_trampa_is_private(direccion):
    # ipaddress marca estas direcciones como is_private; no son RFC 1918.
    assert clasificar_uso(ip(direccion)) != "privada"
    texto = respuesta_cidr(direccion + "/24")["filas"][9]["valor"]
    assert texto != "Privada (RFC 1918)"


@pytest.mark.parametrize("direccion,privada", [
    ("172.15.255.255", False), ("172.16.0.0", True),
    ("172.31.255.255", True), ("172.32.0.0", False),
    ("9.255.255.255", False), ("10.0.0.0", True), ("10.255.255.255", True), ("11.0.0.0", False),
    ("192.167.255.255", False), ("192.168.0.0", True),
    ("192.168.255.255", True), ("192.169.0.0", False),
])
def test_limites_rfc1918(direccion, privada):
    assert (clasificar_uso(ip(direccion)) == "privada") is privada


@pytest.mark.parametrize("direccion,uso", [
    ("0.0.0.0", "no_especificada"),
    ("0.0.0.1", "esta_red"), ("0.255.255.255", "esta_red"),
    ("100.63.255.255", "publica"), ("100.64.0.0", "espacio_compartido"),
    ("100.127.255.255", "espacio_compartido"), ("100.128.0.0", "publica"),
    ("126.255.255.255", "publica"), ("127.0.0.0", "loopback"),
    ("127.255.255.255", "loopback"), ("128.0.0.0", "publica"),
    ("169.253.255.255", "publica"), ("169.254.0.0", "link_local"),
    ("169.254.255.255", "link_local"), ("169.255.0.0", "publica"),
    ("192.0.0.0", "asignaciones_ietf"), ("192.0.0.255", "asignaciones_ietf"),
    ("192.0.1.0", "publica"),
    ("192.0.2.0", "test_net_1"), ("192.0.2.255", "test_net_1"), ("192.0.3.0", "publica"),
    ("192.88.98.255", "publica"), ("192.88.99.0", "retransmision_6to4"),
    ("192.88.99.255", "retransmision_6to4"), ("192.88.100.0", "publica"),
    ("198.17.255.255", "publica"), ("198.18.0.0", "pruebas_rendimiento"),
    ("198.19.255.255", "pruebas_rendimiento"), ("198.20.0.0", "publica"),
    ("198.51.100.0", "test_net_2"), ("198.51.100.255", "test_net_2"),
    ("198.51.101.0", "publica"),
    ("203.0.113.0", "test_net_3"), ("203.0.113.255", "test_net_3"), ("203.0.114.0", "publica"),
    ("223.255.255.255", "publica"),
    ("224.0.0.0", "multicast"), ("239.255.255.255", "multicast"),
    ("240.0.0.0", "reservada"), ("255.255.255.254", "reservada"),
    ("255.255.255.255", "broadcast_limitado"),
    ("8.8.8.8", "publica"), ("1.1.1.1", "publica"),
])
def test_clasificacion_de_uso(direccion, uso):
    assert clasificar_uso(ip(direccion)) == uso


# ---------------------------------------------------------------------------
# Validación: un mensaje por caso, texto exacto
# ---------------------------------------------------------------------------

DIRECCION_MALFORMADA = (
    "Error: la dirección debe tener cuatro octetos numéricos separados por puntos, "
    "por ejemplo 192.168.10.25."
)
MASCARA_MALFORMADA = (
    "Error: la máscara debe tener cuatro octetos numéricos separados por puntos, "
    "por ejemplo 255.255.255.224."
)
FALTA_PREFIJO = (
    "Error: falta el prefijo. Escribe la dirección seguida de /prefijo, "
    "por ejemplo 192.168.10.25/27."
)
PREFIJO_NO_NUMERICO = "Error: el prefijo debe ser un número entero entre 0 y 32, por ejemplo /27."
DIRECCION_VACIA = "Error: escribe una dirección IPv4, por ejemplo 192.168.10.25."
MASCARA_VACIA = "Error: escribe una máscara decimal, por ejemplo 255.255.255.224."
NO_CONTIGUA = (
    "Error: la máscara no es contigua. Debe tener todos los unos seguidos y luego "
    "todos los ceros, por ejemplo 255.255.255.0."
)


def octeto(posicion, valor):
    return (
        "Error: el octeto {} ({}) está fuera de rango. "
        "Cada octeto debe estar entre 0 y 255.".format(posicion, valor)
    )


def prefijo_fuera(valor):
    return "Error: el prefijo /{} está fuera de rango. Debe estar entre 0 y 32.".format(valor)


def mascara_en_prefijo(prefijo):
    return (
        "Error: en este formato el prefijo va como número. Usa /{}, o pasa la máscara "
        "por separado en el formato dirección y máscara.".format(prefijo)
    )


ERRORES_FORMA_A = [
    ("192.168.1.300/24", octeto(4, 300)),
    ("192.168.1.256/24", octeto(4, 256)),
    ("256.1.1.1/8", octeto(1, 256)),
    ("192.168.1.1000/24", octeto(4, 1000)),
    ("192.168.1.10/33", prefijo_fuera(33)),
    ("192.168.1.10/4294967296", prefijo_fuera(4294967296)),
    ("192.168.1.10/-1", PREFIJO_NO_NUMERICO),
    ("192.168.1.10/+8", PREFIJO_NO_NUMERICO),
    ("192.168.1.10/abc", PREFIJO_NO_NUMERICO),
    ("192.168.1.10/ 24", PREFIJO_NO_NUMERICO),
    ("192.168.1.10/24/5", PREFIJO_NO_NUMERICO),
    ("192.168.1.10/²", PREFIJO_NO_NUMERICO),
    ("192.168.1.10", FALTA_PREFIJO),
    ("192.168.1.10/", FALTA_PREFIJO),
    ("192.168.01.10/24", DIRECCION_MALFORMADA),
    ("192.168.1/24", DIRECCION_MALFORMADA),
    ("192.168.1.10.5/24", DIRECCION_MALFORMADA),
    ("a.b.c.d/24", DIRECCION_MALFORMADA),
    ("192.168..10/24", DIRECCION_MALFORMADA),
    ("192.168.1.10 /24", DIRECCION_MALFORMADA),
    ("/24", DIRECCION_MALFORMADA),
    ("0x7f.0.0.1/8", DIRECCION_MALFORMADA),
    ("+1.2.3.4/8", DIRECCION_MALFORMADA),
    ("١٩٢.168.1.1/24", DIRECCION_MALFORMADA),  # dígitos árabe-índicos
    ("192.168.1.²/24", DIRECCION_MALFORMADA),  # "²".isdigit() es True
    ("1" * 70 + "/24", DIRECCION_MALFORMADA),
    ("", DIRECCION_VACIA),
    (" ", DIRECCION_VACIA),
    ("\t \n", DIRECCION_VACIA),
    ("192.168.1.10/255.255.255.0", mascara_en_prefijo(24)),
    ("192.168.1.10/255.255.0.0", mascara_en_prefijo(16)),
    ("192.168.1.10/255.0.255.0", mascara_en_prefijo(24)),
    # La dirección se valida antes que el prefijo.
    ("192.168.1.300/33", octeto(4, 300)),
    ("192.168.1.300", octeto(4, 300)),
    ("192.168.01.10", DIRECCION_MALFORMADA),
]


@pytest.mark.parametrize("entrada,mensaje", ERRORES_FORMA_A)
def test_errores_forma_a(entrada, mensaje):
    with pytest.raises(ErrorValidacion) as error:
        interpretar_cidr(entrada)
    assert error.value.campo == "entrada"
    assert error.value.mensaje == mensaje


ERRORES_FORMA_B = [
    ("192.168.1.10", "255.0.255.0", "mascara", NO_CONTIGUA),
    ("192.168.1.10", "255.255.255.1", "mascara", NO_CONTIGUA),
    ("192.168.1.10", "0.255.255.255", "mascara", NO_CONTIGUA),
    ("192.168.1.10", "255.255.256.0", "mascara", octeto(3, 256)),
    ("192.168.1.10", "255.255.255", "mascara", MASCARA_MALFORMADA),
    ("192.168.1.10", "255.255.255.00", "mascara", MASCARA_MALFORMADA),
    ("192.168.1.10", "/24", "mascara", MASCARA_MALFORMADA),
    ("192.168.1.10", "24", "mascara", MASCARA_MALFORMADA),
    ("192.168.1.10", "", "mascara", MASCARA_VACIA),
    ("192.168.1.10", "   ", "mascara", MASCARA_VACIA),
    ("", "255.255.255.0", "direccion", DIRECCION_VACIA),
    ("", "", "direccion", DIRECCION_VACIA),
    ("192.168.1.300", "255.0.255.0", "direccion", octeto(4, 300)),
    ("192.168.1.10/24", "255.255.255.0", "direccion", DIRECCION_MALFORMADA),
    ("١٩٢.168.1.1", "255.255.255.0", "direccion", DIRECCION_MALFORMADA),
]


@pytest.mark.parametrize("direccion,mascara,campo,mensaje", ERRORES_FORMA_B)
def test_errores_forma_b(direccion, mascara, campo, mensaje):
    with pytest.raises(ErrorValidacion) as error:
        interpretar_direccion_mascara(direccion, mascara)
    assert error.value.campo == campo
    assert error.value.mensaje == mensaje


def test_ningun_mensaje_dice_invalido():
    for _, mensaje in ERRORES_FORMA_A:
        assert mensaje.startswith("Error: ")
        assert "inválid" not in mensaje.lower()


def test_espacios_al_inicio_y_al_final_se_recortan():
    assert interpretar_cidr("  192.168.1.10/24 \t") == (ip("192.168.1.10"), 24)
    assert interpretar_direccion_mascara(" 192.168.1.10 ", " 255.255.255.0 ") == (
        ip("192.168.1.10"), 24,
    )


def test_prefijo_con_ceros_a_la_izquierda_se_acepta():
    # El prefijo no tiene ambigüedad octal: "/024" es 24 (igual que ipaddress).
    assert interpretar_cidr("192.168.1.10/024") == (ip("192.168.1.10"), 24)
    assert interpretar_cidr("192.168.1.10/00") == (ip("192.168.1.10"), 0)


def test_calcular_rechaza_valores_fuera_de_rango():
    with pytest.raises(ValueError):
        calcular(1 << 32, 24)
    with pytest.raises(ValueError):
        calcular(0, 33)


# ---------------------------------------------------------------------------
# Límites y casos especiales
# ---------------------------------------------------------------------------

SIN_SUBRED = {
    "red": None, "broadcast": None, "primer_host": None, "ultimo_host": None,
    "total": None, "hosts": None,
}


def test_0_0_0_0_barra_0_es_ruta_por_defecto():
    respuesta = respuesta_cidr("0.0.0.0/0")
    assert respuesta["datos"] == {
        "direccion": "0.0.0.0", "mascara": "0.0.0.0", "prefijo": 0,
        "clase": "A", "uso": "no_especificada",
        "red": "0.0.0.0", "broadcast": "255.255.255.255",
        "primer_host": "0.0.0.1", "ultimo_host": "255.255.255.254",
        "total": 4294967296, "hosts": 4294967294,
    }
    assert respuesta["nota"] == {
        "titulo": "Prefijo /0.",
        "texto": "Se admite; abarca todo el espacio IPv4 (ruta por defecto).",
    }
    filas = {fila["clave"]: fila["valor"] for fila in respuesta["filas"]}
    assert filas["total"] == "4.294.967.296"
    assert filas["hosts"] == "4.294.967.294"


def test_barra_0_con_otra_direccion():
    respuesta = respuesta_cidr("192.168.1.10/0")
    datos = respuesta["datos"]
    assert (datos["red"], datos["broadcast"]) == ("0.0.0.0", "255.255.255.255")
    assert (datos["primer_host"], datos["ultimo_host"]) == ("0.0.0.1", "255.255.255.254")
    assert (datos["total"], datos["hosts"]) == (4294967296, 4294967294)
    assert (datos["clase"], datos["uso"]) == ("C", "privada")
    assert respuesta["nota"]["titulo"] == "Prefijo /0."


@pytest.mark.parametrize("entrada,mascara", [
    ("255.255.255.255/32", "255.255.255.255"),
    ("255.255.255.255/24", "255.255.255.0"),
])
def test_broadcast_limitado(entrada, mascara):
    respuesta = respuesta_cidr(entrada)
    assert respuesta["datos"] == dict(
        SIN_SUBRED, direccion="255.255.255.255", mascara=mascara,
        prefijo=int(entrada.split("/")[1]), clase="E", uso="broadcast_limitado",
    )
    assert respuesta["nota"]["titulo"] == "Broadcast limitado (255.255.255.255)."
    assert respuesta["binario"]["red"] is None


def test_0_0_0_0_con_prefijo_distinto_de_0():
    respuesta = respuesta_cidr("0.0.0.0/8")
    assert respuesta["datos"] == dict(
        SIN_SUBRED, direccion="0.0.0.0", mascara="255.0.0.0", prefijo=8,
        clase="A", uso="no_especificada",
    )
    assert respuesta["nota"]["titulo"] == "Dirección no especificada (0.0.0.0)."


def test_direccion_que_coincide_con_el_broadcast_del_bloque():
    assert respuesta_cidr("10.255.255.255/8")["datos"] == {
        "direccion": "10.255.255.255", "mascara": "255.0.0.0", "prefijo": 8,
        "clase": "A", "uso": "privada",
        "red": "10.0.0.0", "broadcast": "10.255.255.255",
        "primer_host": "10.0.0.1", "ultimo_host": "10.255.255.254",
        "total": 16777216, "hosts": 16777214,
    }


def test_mascaras_extremas_equivalen_a_barra_0_y_barra_32():
    assert respuesta_direccion_mascara("192.168.1.10", "0.0.0.0") == respuesta_cidr(
        "192.168.1.10/0"
    )
    assert respuesta_direccion_mascara("192.168.1.10", "255.255.255.255") == respuesta_cidr(
        "192.168.1.10/32"
    )


def test_barra_30_es_el_ultimo_prefijo_con_red_y_broadcast():
    datos = respuesta_cidr("192.168.1.6/30")["datos"]
    assert (datos["red"], datos["broadcast"], datos["hosts"]) == ("192.168.1.4", "192.168.1.7", 2)


def test_barra_31_en_mitad_de_red():
    datos = respuesta_cidr("192.168.1.7/31")["datos"]
    assert (datos["primer_host"], datos["ultimo_host"]) == ("192.168.1.6", "192.168.1.7")
    assert (datos["red"], datos["broadcast"], datos["total"], datos["hosts"]) == (None, None, 2, 2)


@pytest.mark.parametrize("entrada", ["224.0.0.1/0", "224.0.0.1/31", "239.255.255.255/32",
                                     "240.0.0.1/0", "240.0.0.1/31", "255.255.255.254/32",
                                     "0.0.0.0/31", "0.0.0.0/32", "255.255.255.255/0"])
def test_direcciones_sin_calculo_de_subred_con_cualquier_prefijo(entrada):
    respuesta = respuesta_cidr(entrada)
    for clave, valor in SIN_SUBRED.items():
        assert respuesta["datos"][clave] == valor
    assert respuesta["binario"]["red"] is None


@pytest.mark.parametrize("entrada,titulo", [
    ("127.0.0.1/32", "Dirección individual (/32)."),   # /32 antes que loopback
    ("169.254.0.1/31", "Enlace punto a punto (RFC 3021)."),  # /31 antes que link-local
    ("127.0.0.1/0", "Prefijo /0."),
    ("0.0.0.0/0", "Prefijo /0."),
    # Decisión documentada: si la dirección no admite cálculo de subred,
    # su nota gana a la del prefijo (si no, contradiría las filas "No aplica").
    ("224.0.0.1/32", "Dirección multicast (clase D)."),
    ("224.0.0.1/31", "Dirección multicast (clase D)."),
    ("240.0.0.1/0", "Dirección reservada (clase E)."),
    ("0.0.0.0/32", "Dirección no especificada (0.0.0.0)."),
    ("255.255.255.255/32", "Broadcast limitado (255.255.255.255)."),
    ("10.0.0.1/24", None),
    ("100.64.0.1/10", None),
])
def test_prioridad_de_notas(entrada, titulo):
    nota = respuesta_cidr(entrada)["nota"]
    assert (None if nota is None else nota["titulo"]) == titulo
