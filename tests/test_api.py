"""Pruebas de la API: códigos HTTP, forma exacta del JSON y equivalencias."""

import json

import pytest

from app import create_app
from calc.casos import CASOS_DE_PRUEBA


@pytest.fixture()
def cliente():
    return create_app().test_client()


def post(cliente, cuerpo):
    return cliente.post("/api/calcular", json=cuerpo)


def get(cliente, **parametros):
    return cliente.get("/api/calcular", query_string=parametros)


# Respuesta completa esperada para 192.168.1.100/24, escrita a mano según el contrato.
ESPERADO_192_168_1_100_24 = {
    "ok": True,
    "entrada": {
        "direccion": "192.168.1.100", "mascara": "255.255.255.0", "prefijo": 24,
        "texto": "192.168.1.100 · máscara 255.255.255.0 · /24",
    },
    "nota": None,
    "filas": [
        {"clave": "red", "etiqueta": "Dirección de red", "valor": "192.168.1.0", "aplica": True, "mono": True},
        {"clave": "broadcast", "etiqueta": "Broadcast dirigido", "valor": "192.168.1.255", "aplica": True, "mono": True},
        {"clave": "primer_host", "etiqueta": "Primer host utilizable", "valor": "192.168.1.1", "aplica": True, "mono": True},
        {"clave": "ultimo_host", "etiqueta": "Último host utilizable", "valor": "192.168.1.254", "aplica": True, "mono": True},
        {"clave": "total", "etiqueta": "Direcciones en el bloque", "valor": "256", "aplica": True, "mono": True},
        {"clave": "hosts", "etiqueta": "Hosts utilizables", "valor": "254", "aplica": True, "mono": True},
        {"clave": "mascara", "etiqueta": "Máscara decimal", "valor": "255.255.255.0", "aplica": True, "mono": True},
        {"clave": "prefijo", "etiqueta": "Prefijo CIDR", "valor": "/24", "aplica": True, "mono": True},
        {"clave": "clase", "etiqueta": "Clase tradicional", "valor": "C", "aplica": True, "mono": False},
        {"clave": "uso", "etiqueta": "Clasificación de uso", "valor": "Privada (RFC 1918)", "aplica": True, "mono": False},
    ],
    "binario": {
        "direccion": "11000000.10101000.00000001.01100100",
        "mascara": "11111111.11111111.11111111.00000000",
        "red": "11000000.10101000.00000001.00000000",
        "bits_red": 24,
    },
    "datos": {
        "direccion": "192.168.1.100", "mascara": "255.255.255.0", "prefijo": 24,
        "clase": "C", "uso": "privada",
        "red": "192.168.1.0", "broadcast": "192.168.1.255",
        "primer_host": "192.168.1.1", "ultimo_host": "192.168.1.254",
        "total": 256, "hosts": 254,
    },
}


def valores(respuesta):
    return {fila["clave"]: (fila["valor"], fila["aplica"]) for fila in respuesta["filas"]}


# ---------------------------------------------------------------------------
# Rutas auxiliares
# ---------------------------------------------------------------------------

def test_salud(cliente):
    respuesta = cliente.get("/api/salud")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"ok": True}


def test_casos_de_prueba(cliente):
    respuesta = cliente.get("/api/casos-de-prueba")
    assert respuesta.status_code == 200
    assert respuesta.get_json() == [
        {"entrada": "192.168.1.100/24", "etiqueta": "Clase C, privada"},
        {"entrada": "172.16.10.50/30", "etiqueta": "2 hosts"},
        {"entrada": "10.0.0.0/31", "etiqueta": "RFC 3021"},
        {"entrada": "192.168.1.25/32", "etiqueta": "Host único"},
        {"entrada": "224.0.0.1/24", "etiqueta": "Clase D"},
        {"entrada": "240.0.0.1/24", "etiqueta": "Clase E"},
        {"entrada": "127.0.0.1/8", "etiqueta": "Loopback"},
        {"entrada": "169.254.10.20/16", "etiqueta": "Link-local"},
        {"entrada": "192.168.1.300/24", "etiqueta": "Error"},
        {"entrada": "192.168.1.10/33", "etiqueta": "Error"},
        {"direccion": "192.168.1.10", "mascara": "255.0.255.0", "etiqueta": "Error"},
    ]


# ---------------------------------------------------------------------------
# Respuesta correcta
# ---------------------------------------------------------------------------

def test_forma_exacta_de_la_respuesta(cliente):
    respuesta = post(cliente, {"entrada": "192.168.1.100/24"})
    assert respuesta.status_code == 200
    assert respuesta.mimetype == "application/json"
    cuerpo = respuesta.get_json()
    assert cuerpo == ESPERADO_192_168_1_100_24
    # El orden de las claves también forma parte del contrato.
    assert list(cuerpo) == ["ok", "entrada", "nota", "filas", "binario", "datos"]
    assert list(cuerpo["datos"]) == list(ESPERADO_192_168_1_100_24["datos"])


def test_json_en_utf8_legible(cliente):
    crudo = post(cliente, {"entrada": "192.168.1.100/24"}).get_data(as_text=True)
    assert "Dirección de red" in crudo
    assert "\\u00f3" not in crudo


def test_filas_barra_31(cliente):
    respuesta = post(cliente, {"entrada": "10.0.0.0/31"}).get_json()
    assert valores(respuesta) == {
        "red": ("No se reserva (RFC 3021)", False),
        "broadcast": ("No aplica en este enlace", False),
        "primer_host": ("10.0.0.0", True),
        "ultimo_host": ("10.0.0.1", True),
        "total": ("2", True),
        "hosts": ("2", True),
        "mascara": ("255.255.255.254", True),
        "prefijo": ("/31", True),
        "clase": ("A", True),
        "uso": ("Privada (RFC 1918)", True),
    }
    assert respuesta["nota"] == {
        "titulo": "Enlace punto a punto (RFC 3021).",
        "texto": "Con prefijo /31 las dos direcciones del bloque se asignan a los extremos "
                 "del enlace. No se reservan dirección de red ni broadcast dirigido.",
    }
    assert respuesta["binario"]["red"] == "00001010.00000000.00000000.00000000"


def test_filas_barra_32(cliente):
    respuesta = post(cliente, {"entrada": "192.168.1.25/32"}).get_json()
    assert valores(respuesta) == {
        "red": ("192.168.1.25", True),
        "broadcast": ("No aplica", False),
        "primer_host": ("No aplica", False),
        "ultimo_host": ("No aplica", False),
        "total": ("1", True),
        "hosts": ("No aplica (ruta de host)", False),
        "mascara": ("255.255.255.255", True),
        "prefijo": ("/32", True),
        "clase": ("C", True),
        "uso": ("Privada (RFC 1918)", True),
    }
    assert respuesta["nota"] == {
        "titulo": "Dirección individual (/32).",
        "texto": "Identifica un solo host o una ruta de host; no se aplica la fórmula "
                 "de hosts útiles de una subred.",
    }


@pytest.mark.parametrize("entrada,clase,uso,nota", [
    ("224.0.0.1/24", "D (multicast)", "Propósito especial: multicast", (
        "Dirección multicast (clase D).",
        "El rango 224.0.0.0 – 239.255.255.255 identifica grupos, no hosts. "
        "No se calculan red, broadcast ni hosts utilizables.",
    )),
    ("240.0.0.1/24", "E (reservada)", "Propósito especial: reservada (240.0.0.0/4)", (
        "Dirección reservada (clase E).",
        "El rango 240.0.0.0 – 255.255.255.254 es de uso especial; no se trata como "
        "host unicast.",
    )),
    ("255.255.255.255/24", "E (reservada)", "Propósito especial: broadcast limitado", (
        "Broadcast limitado (255.255.255.255).",
        "Se entrega a todos los equipos del enlace local y nunca se enruta. "
        "No se calculan red, broadcast ni hosts utilizables.",
    )),
    ("0.0.0.0/8", "A", "Propósito especial: no especificada", (
        "Dirección no especificada (0.0.0.0).",
        "No identifica un host concreto; se usa cuando aún no se tiene dirección. "
        "No se calculan red, broadcast ni hosts utilizables.",
    )),
])
def test_filas_sin_calculo_de_subred(cliente, entrada, clase, uso, nota):
    respuesta = post(cliente, {"entrada": entrada}).get_json()
    filas = valores(respuesta)
    for clave in ("red", "broadcast", "primer_host", "ultimo_host", "total", "hosts"):
        assert filas[clave] == ("No aplica", False)
    assert filas["mascara"][1] and filas["prefijo"][1]
    assert filas["clase"] == (clase, True)
    assert filas["uso"] == (uso, True)
    assert respuesta["nota"] == {"titulo": nota[0], "texto": nota[1]}
    assert respuesta["binario"]["red"] is None
    assert respuesta["binario"]["bits_red"] == respuesta["entrada"]["prefijo"]


@pytest.mark.parametrize("entrada,nota", [
    ("127.0.0.1/8", ("Dirección de loopback (127.0.0.0/8).",
                     "Identifica al propio equipo y no sale a la red.")),
    ("169.254.10.20/16", ("Dirección link-local (169.254.0.0/16).",
                          "Solo es válida dentro del enlace local y no se enruta.")),
])
def test_notas_loopback_y_link_local(cliente, entrada, nota):
    respuesta = post(cliente, {"entrada": entrada}).get_json()
    assert respuesta["nota"] == {"titulo": nota[0], "texto": nota[1]}


def test_miles_con_punto(cliente):
    filas = valores(post(cliente, {"entrada": "127.0.0.1/8"}).get_json())
    assert filas["total"] == ("16.777.216", True)
    assert filas["hosts"] == ("16.777.214", True)
    filas = valores(post(cliente, {"entrada": "10.0.0.1/22"}).get_json())
    assert filas["total"] == ("1.024", True)


@pytest.mark.parametrize("entrada", [
    "192.168.1.100/24", "10.0.0.0/31", "192.168.1.25/32", "224.0.0.1/24", "0.0.0.0/0",
    "240.0.0.1/24", "255.255.255.255/32", "8.8.8.8/0",
])
def test_aplica_coincide_con_datos_nulos(cliente, entrada):
    respuesta = post(cliente, {"entrada": entrada}).get_json()
    assert len(respuesta["filas"]) == 10
    for fila in respuesta["filas"]:
        if fila["clave"] in respuesta["datos"] and fila["clave"] not in ("mascara", "prefijo",
                                                                         "clase", "uso"):
            assert fila["aplica"] == (respuesta["datos"][fila["clave"]] is not None), fila
        assert isinstance(fila["valor"], str)


# ---------------------------------------------------------------------------
# Equivalencias: forma A = forma B, GET = POST
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entrada,mascara", [
    ("192.168.1.100/24", "255.255.255.0"),
    ("192.168.10.25/27", "255.255.255.224"),
    ("10.0.0.0/31", "255.255.255.254"),
    ("192.168.1.25/32", "255.255.255.255"),
    ("224.0.0.1/24", "255.255.255.0"),
    ("0.0.0.0/0", "0.0.0.0"),
])
def test_formas_y_metodos_equivalentes(cliente, entrada, mascara):
    direccion = entrada.split("/")[0]
    respuestas = [
        post(cliente, {"entrada": entrada}),
        post(cliente, {"direccion": direccion, "mascara": mascara}),
        get(cliente, entrada=entrada),
        get(cliente, direccion=direccion, mascara=mascara),
    ]
    assert {r.status_code for r in respuestas} == {200}
    cuerpos = [r.get_data() for r in respuestas]
    assert cuerpos.count(cuerpos[0]) == 4  # byte a byte idénticos


def test_casos_de_prueba_responden_con_el_codigo_esperado(cliente):
    codigos = []
    for caso in CASOS_DE_PRUEBA:
        cuerpo = {clave: valor for clave, valor in caso.items() if clave != "etiqueta"}
        codigos.append(post(cliente, cuerpo).status_code)
    assert codigos == [200] * 8 + [422] * 3


# ---------------------------------------------------------------------------
# Errores de validación (422)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cuerpo,campo,mensaje", [
    ({"entrada": "192.168.1.300/24"}, "entrada",
     "Error: el octeto 4 (300) está fuera de rango. Cada octeto debe estar entre 0 y 255."),
    ({"entrada": "192.168.1.10/33"}, "entrada",
     "Error: el prefijo /33 está fuera de rango. Debe estar entre 0 y 32."),
    ({"direccion": "192.168.1.10", "mascara": "255.0.255.0"}, "mascara",
     "Error: la máscara no es contigua. Debe tener todos los unos seguidos y luego "
     "todos los ceros, por ejemplo 255.255.255.0."),
    ({"direccion": "192.168.1.300", "mascara": "255.255.255.0"}, "direccion",
     "Error: el octeto 4 (300) está fuera de rango. Cada octeto debe estar entre 0 y 255."),
    ({"direccion": "192.168.1.10", "mascara": "255.255.300.0"}, "mascara",
     "Error: el octeto 3 (300) está fuera de rango. Cada octeto debe estar entre 0 y 255."),
    ({"entrada": "   "}, "entrada", "Error: escribe una dirección IPv4, por ejemplo 192.168.10.25."),
    ({"direccion": "192.168.1.10"}, "mascara",
     "Error: escribe una máscara decimal, por ejemplo 255.255.255.224."),
    ({"mascara": "255.255.255.0"}, "direccion",
     "Error: escribe una dirección IPv4, por ejemplo 192.168.10.25."),
])
def test_error_de_validacion(cliente, cuerpo, campo, mensaje):
    for respuesta in (post(cliente, cuerpo), get(cliente, **cuerpo)):
        assert respuesta.status_code == 422
        assert respuesta.get_json() == {"ok": False, "errores": [{"campo": campo, "mensaje": mensaje}]}


# ---------------------------------------------------------------------------
# Errores de la petición (400) y otros códigos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("crudo", ['{"entrada": "192.168.1.1/24"', "no es json", "", "[" * 3000])
def test_json_mal_formado(cliente, crudo):
    respuesta = cliente.post("/api/calcular", data=crudo, content_type="application/json")
    assert respuesta.status_code == 400
    cuerpo = respuesta.get_json()
    assert cuerpo["ok"] is False
    assert cuerpo["errores"][0]["campo"] == "cuerpo"
    assert cuerpo["errores"][0]["mensaje"].startswith("Error: ")


@pytest.mark.parametrize("crudo", ['["192.168.1.1/24"]', '"192.168.1.1/24"', "null", "42"])
def test_json_que_no_es_objeto(cliente, crudo):
    respuesta = cliente.post("/api/calcular", data=crudo, content_type="application/json")
    assert respuesta.status_code == 400
    assert respuesta.get_json()["errores"][0]["campo"] == "cuerpo"


def test_formas_a_y_b_a_la_vez(cliente):
    cuerpo = {"entrada": "192.168.1.1/24", "direccion": "192.168.1.1", "mascara": "255.255.255.0"}
    for respuesta in (post(cliente, cuerpo), get(cliente, **cuerpo)):
        assert respuesta.status_code == 400
        assert respuesta.get_json() == {"ok": False, "errores": [{
            "campo": "peticion",
            "mensaje": 'Error: usa un solo formato: "entrada", o bien "direccion" y '
                       '"mascara", pero no los dos a la vez.',
        }]}
    assert post(cliente, {"entrada": "1.1.1.1/8", "mascara": "255.0.0.0"}).status_code == 400


def test_sin_datos(cliente):
    assert post(cliente, {}).status_code == 400
    assert post(cliente, {"otra": "cosa"}).status_code == 400
    assert cliente.get("/api/calcular").status_code == 400


@pytest.mark.parametrize("cuerpo", [
    {"entrada": 24}, {"entrada": None}, {"entrada": ["192.168.1.1/24"]},
    {"direccion": "192.168.1.1", "mascara": 24},
])
def test_campos_que_no_son_texto(cliente, cuerpo):
    respuesta = post(cliente, cuerpo)
    assert respuesta.status_code == 400
    assert respuesta.get_json()["errores"][0]["campo"] == "peticion"


def test_ignora_el_content_type(cliente):
    respuesta = cliente.post("/api/calcular", data=json.dumps({"entrada": "10.0.0.1/8"}),
                             content_type="text/plain")
    assert respuesta.status_code == 200


def test_cuerpo_demasiado_grande(cliente):
    respuesta = cliente.post("/api/calcular", data="x" * 10000, content_type="application/json")
    assert respuesta.status_code == 413
    assert respuesta.get_json()["ok"] is False


def test_ruta_inexistente_responde_json(cliente):
    respuesta = cliente.get("/api/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.get_json()["ok"] is False


def test_metodo_no_permitido_responde_json(cliente):
    respuesta = cliente.delete("/api/calcular")
    assert respuesta.status_code == 405
    assert respuesta.get_json()["ok"] is False
    assert "POST" in respuesta.headers["Allow"]


def test_fallo_inesperado_responde_500_json():
    app = create_app()

    @app.get("/api/fallo")
    def fallo():
        raise RuntimeError("prueba")

    respuesta = app.test_client().get("/api/fallo")
    assert respuesta.status_code == 500
    assert respuesta.get_json()["errores"][0]["mensaje"] == (
        "Error: fallo interno del servidor. Inténtalo de nuevo."
    )


def test_sin_cabeceras_cors(cliente):
    respuesta = post(cliente, {"entrada": "192.168.1.100/24"})
    assert "Access-Control-Allow-Origin" not in respuesta.headers
