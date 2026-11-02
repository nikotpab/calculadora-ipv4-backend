"""Genera la tabla de pruebas del informe (apartado 6) en Markdown.

Ejecuta cada caso contra el módulo de cálculo y lo compara con el resultado
esperado, que está escrito a mano en este archivo (no se calcula con el
código que se prueba ni se toma de calc/mensajes.py).

Uso:
    python scripts/tabla_pruebas.py                       # imprime la tabla
    python scripts/tabla_pruebas.py --salida tabla-pruebas.md

Termina con código 1 si algún caso no coincide.
"""

import argparse
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from calc.ipv4 import ErrorValidacion  # noqa: E402
from calc.respuesta import respuesta_cidr, respuesta_direccion_mascara  # noqa: E402

NA = "No aplica"
PRIVADA = "Privada (RFC 1918)"
PUBLICA = "Pública global"


def ok(red, broadcast, primer, ultimo, total, hosts, mascara, prefijo, clase, uso, nota=None):
    """Resultado esperado de un cálculo correcto, con los textos que ve el usuario."""
    return {
        "red": red, "broadcast": broadcast, "primer_host": primer, "ultimo_host": ultimo,
        "total": total, "hosts": hosts, "mascara": mascara, "prefijo": prefijo,
        "clase": clase, "uso": uso, "nota": nota,
    }


def sin_subred(mascara, prefijo, clase, uso, nota):
    return ok(NA, NA, NA, NA, NA, NA, mascara, prefijo, clase, uso, nota)


def error(campo, mensaje):
    return {"campo": campo, "error": mensaje}


def octeto(posicion, valor):
    return ("Error: el octeto {} ({}) está fuera de rango. Cada octeto debe estar "
            "entre 0 y 255.".format(posicion, valor))


DIR_MALFORMADA = ("Error: la dirección debe tener cuatro octetos numéricos separados por "
                  "puntos, por ejemplo 192.168.10.25.")
NO_CONTIGUA = ("Error: la máscara no es contigua. Debe tener todos los unos seguidos y "
               "luego todos los ceros, por ejemplo 255.255.255.0.")

# (entrada, esperado). La entrada es un texto (forma A) o una tupla
# (dirección, máscara) (forma B).
CASOS_MINIMOS = [
    ("192.168.1.100/24", ok("192.168.1.0", "192.168.1.255", "192.168.1.1", "192.168.1.254",
                            "256", "254", "255.255.255.0", "/24", "C", PRIVADA)),
    ("172.16.10.50/30", ok("172.16.10.48", "172.16.10.51", "172.16.10.49", "172.16.10.50",
                           "4", "2", "255.255.255.252", "/30", "B", PRIVADA)),
    ("10.0.0.0/31", ok("No se reserva (RFC 3021)", "No aplica en este enlace", "10.0.0.0",
                       "10.0.0.1", "2", "2", "255.255.255.254", "/31", "A", PRIVADA,
                       "Enlace punto a punto (RFC 3021).")),
    ("192.168.1.25/32", ok("192.168.1.25", NA, NA, NA, "1", "No aplica (ruta de host)",
                           "255.255.255.255", "/32", "C", PRIVADA,
                           "Dirección individual (/32).")),
    ("224.0.0.1/24", sin_subred("255.255.255.0", "/24", "D (multicast)",
                                "Propósito especial: multicast",
                                "Dirección multicast (clase D).")),
    ("240.0.0.1/24", sin_subred("255.255.255.0", "/24", "E (reservada)",
                                "Propósito especial: reservada (240.0.0.0/4)",
                                "Dirección reservada (clase E).")),
    ("127.0.0.1/8", ok("127.0.0.0", "127.255.255.255", "127.0.0.1", "127.255.255.254",
                       "16.777.216", "16.777.214", "255.0.0.0", "/8", "A",
                       "Propósito especial: loopback", "Dirección de loopback (127.0.0.0/8).")),
    ("169.254.10.20/16", ok("169.254.0.0", "169.254.255.255", "169.254.0.1", "169.254.255.254",
                            "65.536", "65.534", "255.255.0.0", "/16", "B",
                            "Propósito especial: link-local",
                            "Dirección link-local (169.254.0.0/16).")),
    ("192.168.1.300/24", error("entrada", octeto(4, 300))),
    ("192.168.1.10/33", error("entrada", "Error: el prefijo /33 está fuera de rango. "
                                         "Debe estar entre 0 y 32.")),
    (("192.168.1.10", "255.0.255.0"), error("mascara", NO_CONTIGUA)),
]

TODO_EL_ESPACIO = ("0.0.0.0", "255.255.255.255", "0.0.0.1", "255.255.255.254",
                   "4.294.967.296", "4.294.967.294", "0.0.0.0", "/0")

CASOS_EXTRA = [
    ("192.168.10.25/27", ok("192.168.10.0", "192.168.10.31", "192.168.10.1", "192.168.10.30",
                            "32", "30", "255.255.255.224", "/27", "C", PRIVADA)),
    (("192.168.10.25", "255.255.255.224"),
     ok("192.168.10.0", "192.168.10.31", "192.168.10.1", "192.168.10.30",
        "32", "30", "255.255.255.224", "/27", "C", PRIVADA)),
    ("8.8.8.8/24", ok("8.8.8.0", "8.8.8.255", "8.8.8.1", "8.8.8.254", "256", "254",
                      "255.255.255.0", "/24", "A", PUBLICA)),
    ("10.255.255.255/8", ok("10.0.0.0", "10.255.255.255", "10.0.0.1", "10.255.255.254",
                            "16.777.216", "16.777.214", "255.0.0.0", "/8", "A", PRIVADA)),
    ("172.31.255.255/12", ok("172.16.0.0", "172.31.255.255", "172.16.0.1", "172.31.255.254",
                             "1.048.576", "1.048.574", "255.240.0.0", "/12", "B", PRIVADA)),
    ("172.32.0.1/12", ok("172.32.0.0", "172.47.255.255", "172.32.0.1", "172.47.255.254",
                         "1.048.576", "1.048.574", "255.240.0.0", "/12", "B", PUBLICA)),
    ("100.64.0.1/10", ok("100.64.0.0", "100.127.255.255", "100.64.0.1", "100.127.255.254",
                         "4.194.304", "4.194.302", "255.192.0.0", "/10", "A",
                         "Propósito especial: espacio compartido (CGNAT)")),
    ("0.0.0.0/0", ok(*TODO_EL_ESPACIO, "A", "Propósito especial: no especificada",
                     "Prefijo /0.")),
    ("192.168.1.10/0", ok(*TODO_EL_ESPACIO, "C", PRIVADA, "Prefijo /0.")),
    (("192.168.1.10", "0.0.0.0"), ok(*TODO_EL_ESPACIO, "C", PRIVADA, "Prefijo /0.")),
    (("192.168.1.10", "255.255.255.255"),
     ok("192.168.1.10", NA, NA, NA, "1", "No aplica (ruta de host)", "255.255.255.255", "/32",
        "C", PRIVADA, "Dirección individual (/32).")),
    ("0.0.0.0/8", sin_subred("255.0.0.0", "/8", "A", "Propósito especial: no especificada",
                             "Dirección no especificada (0.0.0.0).")),
    ("255.255.255.255/32", sin_subred("255.255.255.255", "/32", "E (reservada)",
                                      "Propósito especial: broadcast limitado",
                                      "Broadcast limitado (255.255.255.255).")),
    ("255.255.255.255/24", sin_subred("255.255.255.0", "/24", "E (reservada)",
                                      "Propósito especial: broadcast limitado",
                                      "Broadcast limitado (255.255.255.255).")),
    ("224.0.0.1/32", sin_subred("255.255.255.255", "/32", "D (multicast)",
                                "Propósito especial: multicast",
                                "Dirección multicast (clase D).")),
    ("192.168.1.10/255.255.255.0", error(
        "entrada", "Error: en este formato el prefijo va como número. Usa /24, o pasa la "
                   "máscara por separado en el formato dirección y máscara.")),
    ("192.168.01.10/24", error("entrada", DIR_MALFORMADA)),
    ("١٩٢.168.1.1/24", error("entrada", DIR_MALFORMADA)),
    ("192.168.1.10", error("entrada", "Error: falta el prefijo. Escribe la dirección seguida "
                                      "de /prefijo, por ejemplo 192.168.10.25/27.")),
    ("192.168.1.10/abc", error("entrada", "Error: el prefijo debe ser un número entero entre "
                                          "0 y 32, por ejemplo /27.")),
    ("", error("entrada", "Error: escribe una dirección IPv4, por ejemplo 192.168.10.25.")),
    (("192.168.1.10", "255.255.255.1"), error("mascara", NO_CONTIGUA)),
    (("192.168.1.10", "255.255.256.0"), error("mascara", octeto(3, 256))),
]

ETIQUETAS = (
    ("red", "Red"), ("broadcast", "Broadcast"), ("primer_host", "Primer host"),
    ("ultimo_host", "Último host"), ("total", "Total"), ("hosts", "Hosts utilizables"),
    ("mascara", "Máscara"), ("prefijo", "Prefijo"), ("clase", "Clase"), ("uso", "Uso"),
    ("nota", "Nota"),
)


def obtener(entrada):
    """Ejecuta el caso y lo reduce a los textos que ve el usuario."""
    try:
        if isinstance(entrada, tuple):
            respuesta = respuesta_direccion_mascara(*entrada)
        else:
            respuesta = respuesta_cidr(entrada)
    except ErrorValidacion as fallo:
        return error(fallo.campo, fallo.mensaje)
    obtenido = {fila["clave"]: fila["valor"] for fila in respuesta["filas"]}
    obtenido["nota"] = respuesta["nota"]["titulo"] if respuesta["nota"] else None
    return obtenido


def describir(resultado):
    if "error" in resultado:
        return "HTTP 422, campo {}: {}".format(resultado["campo"], resultado["error"])
    partes = ["{}: {}".format(etiqueta, resultado[clave])
              for clave, etiqueta in ETIQUETAS if resultado.get(clave) is not None]
    return "; ".join(partes)


def describir_entrada(entrada):
    if isinstance(entrada, tuple):
        return "{} + {}".format(*entrada)
    return entrada if entrada.strip() else '"{}" (vacío)'.format(entrada)


def celda(texto):
    return texto.replace("|", "\\|")


def tabla(titulo, casos):
    lineas = [
        "## " + titulo, "",
        "| Entrada | Resultado esperado | Resultado obtenido | ¿Coincide? |",
        "|---|---|---|---|",
    ]
    coinciden = 0
    for entrada, esperado in casos:
        obtenido = obtener(entrada)
        igual = obtenido == esperado
        coinciden += igual
        lineas.append("| {} | {} | {} | {} |".format(
            celda(describir_entrada(entrada)), celda(describir(esperado)),
            celda(describir(obtenido)), "Sí" if igual else "**No**",
        ))
    lineas += ["", "{} de {} casos coinciden.".format(coinciden, len(casos)), ""]
    return lineas, coinciden == len(casos)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", help="archivo Markdown donde escribir la tabla")
    argumentos = parser.parse_args()

    minimos, ok_minimos = tabla("Casos mínimos del enunciado", CASOS_MINIMOS)
    extra, ok_extra = tabla("Casos adicionales (límites y validación)", CASOS_EXTRA)
    documento = "\n".join([
        "# Tabla de pruebas", "",
        "Generada con `python scripts/tabla_pruebas.py`. Los resultados esperados están "
        "escritos a mano en el script; los obtenidos salen de ejecutar el módulo de "
        "cálculo (`calc/`). La forma \"a.b.c.d + máscara\" usa el formato dirección y "
        "máscara.", "",
    ] + minimos + extra)

    todo_ok = ok_minimos and ok_extra
    if argumentos.salida:
        ruta = pathlib.Path(argumentos.salida)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(documento, encoding="utf-8")
        print("Tabla escrita en {}. {}".format(
            ruta, "Todos los casos coinciden." if todo_ok else "HAY CASOS QUE NO COINCIDEN."))
    else:
        sys.stdout.write(documento)
    return 0 if todo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
