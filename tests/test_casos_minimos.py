"""Los 11 casos mínimos del enunciado, con todos los campos de ``datos``.

Los valores esperados están escritos a mano a partir del enunciado; no se
calculan con el código que se prueba.
"""

import pytest

from calc.casos import CASOS_DE_PRUEBA
from calc.ipv4 import ErrorValidacion
from calc.respuesta import respuesta_cidr, respuesta_direccion_mascara

# entrada A, máscara para la forma B, datos esperados
CASOS_VALIDOS = [
    (
        "192.168.1.100/24", "255.255.255.0",
        {
            "direccion": "192.168.1.100", "mascara": "255.255.255.0", "prefijo": 24,
            "clase": "C", "uso": "privada",
            "red": "192.168.1.0", "broadcast": "192.168.1.255",
            "primer_host": "192.168.1.1", "ultimo_host": "192.168.1.254",
            "total": 256, "hosts": 254,
        },
    ),
    (
        "172.16.10.50/30", "255.255.255.252",
        {
            "direccion": "172.16.10.50", "mascara": "255.255.255.252", "prefijo": 30,
            "clase": "B", "uso": "privada",
            "red": "172.16.10.48", "broadcast": "172.16.10.51",
            "primer_host": "172.16.10.49", "ultimo_host": "172.16.10.50",
            "total": 4, "hosts": 2,
        },
    ),
    (
        "10.0.0.0/31", "255.255.255.254",
        {
            "direccion": "10.0.0.0", "mascara": "255.255.255.254", "prefijo": 31,
            "clase": "A", "uso": "privada",
            "red": None, "broadcast": None,
            "primer_host": "10.0.0.0", "ultimo_host": "10.0.0.1",
            "total": 2, "hosts": 2,
        },
    ),
    (
        "192.168.1.25/32", "255.255.255.255",
        {
            "direccion": "192.168.1.25", "mascara": "255.255.255.255", "prefijo": 32,
            "clase": "C", "uso": "privada",
            "red": "192.168.1.25", "broadcast": None,
            "primer_host": None, "ultimo_host": None,
            "total": 1, "hosts": None,
        },
    ),
    (
        "224.0.0.1/24", "255.255.255.0",
        {
            "direccion": "224.0.0.1", "mascara": "255.255.255.0", "prefijo": 24,
            "clase": "D", "uso": "multicast",
            "red": None, "broadcast": None, "primer_host": None, "ultimo_host": None,
            "total": None, "hosts": None,
        },
    ),
    (
        "240.0.0.1/24", "255.255.255.0",
        {
            "direccion": "240.0.0.1", "mascara": "255.255.255.0", "prefijo": 24,
            "clase": "E", "uso": "reservada",
            "red": None, "broadcast": None, "primer_host": None, "ultimo_host": None,
            "total": None, "hosts": None,
        },
    ),
    (
        "127.0.0.1/8", "255.0.0.0",
        {
            "direccion": "127.0.0.1", "mascara": "255.0.0.0", "prefijo": 8,
            "clase": "A", "uso": "loopback",
            "red": "127.0.0.0", "broadcast": "127.255.255.255",
            "primer_host": "127.0.0.1", "ultimo_host": "127.255.255.254",
            "total": 16777216, "hosts": 16777214,
        },
    ),
    (
        "169.254.10.20/16", "255.255.0.0",
        {
            "direccion": "169.254.10.20", "mascara": "255.255.0.0", "prefijo": 16,
            "clase": "B", "uso": "link_local",
            "red": "169.254.0.0", "broadcast": "169.254.255.255",
            "primer_host": "169.254.0.1", "ultimo_host": "169.254.255.254",
            "total": 65536, "hosts": 65534,
        },
    ),
]

NOTA_ESPERADA = {
    "192.168.1.100/24": None,
    "172.16.10.50/30": None,
    "10.0.0.0/31": "Enlace punto a punto (RFC 3021).",
    "192.168.1.25/32": "Dirección individual (/32).",
    "224.0.0.1/24": "Dirección multicast (clase D).",
    "240.0.0.1/24": "Dirección reservada (clase E).",
    "127.0.0.1/8": "Dirección de loopback (127.0.0.0/8).",
    "169.254.10.20/16": "Dirección link-local (169.254.0.0/16).",
}


@pytest.mark.parametrize("entrada,mascara,datos", CASOS_VALIDOS, ids=[c[0] for c in CASOS_VALIDOS])
def test_caso_minimo_datos(entrada, mascara, datos):
    assert respuesta_cidr(entrada)["datos"] == datos


@pytest.mark.parametrize("entrada,mascara,datos", CASOS_VALIDOS, ids=[c[0] for c in CASOS_VALIDOS])
def test_caso_minimo_formas_a_y_b_iguales(entrada, mascara, datos):
    direccion = entrada.split("/")[0]
    assert respuesta_direccion_mascara(direccion, mascara) == respuesta_cidr(entrada)


@pytest.mark.parametrize("entrada", list(NOTA_ESPERADA))
def test_caso_minimo_nota(entrada):
    nota = respuesta_cidr(entrada)["nota"]
    titulo = None if nota is None else nota["titulo"]
    assert titulo == NOTA_ESPERADA[entrada]


def test_octeto_fuera_de_rango():
    with pytest.raises(ErrorValidacion) as error:
        respuesta_cidr("192.168.1.300/24")
    assert error.value.campo == "entrada"
    assert error.value.mensaje == (
        "Error: el octeto 4 (300) está fuera de rango. Cada octeto debe estar entre 0 y 255."
    )


def test_prefijo_fuera_de_rango():
    with pytest.raises(ErrorValidacion) as error:
        respuesta_cidr("192.168.1.10/33")
    assert error.value.campo == "entrada"
    assert error.value.mensaje == (
        "Error: el prefijo /33 está fuera de rango. Debe estar entre 0 y 32."
    )


def test_mascara_no_contigua():
    with pytest.raises(ErrorValidacion) as error:
        respuesta_direccion_mascara("192.168.1.10", "255.0.255.0")
    assert error.value.campo == "mascara"
    assert error.value.mensaje == (
        "Error: la máscara no es contigua. Debe tener todos los unos seguidos y "
        "luego todos los ceros, por ejemplo 255.255.255.0."
    )


def test_lista_de_casos_coincide_con_el_enunciado():
    assert [caso.get("entrada") for caso in CASOS_DE_PRUEBA[:10]] == [
        c[0] for c in CASOS_VALIDOS
    ] + ["192.168.1.300/24", "192.168.1.10/33"]
    assert CASOS_DE_PRUEBA[10] == {
        "direccion": "192.168.1.10", "mascara": "255.0.255.0", "etiqueta": "Error",
    }
