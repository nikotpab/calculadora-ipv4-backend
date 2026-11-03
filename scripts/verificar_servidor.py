"""Prueba los 15 casos del informe contra una API en ejecución, por HTTP.

Solo usa la biblioteca estándar, así que corre desde cualquier equipo con
Python 3 (no hace falta instalar nada). Los valores esperados están escritos
a mano aquí; no se importan del código de la aplicación.

Uso:
    python3 scripts/verificar_servidor.py http://IP_DEL_SERVIDOR
    python3 scripts/verificar_servidor.py http://127.0.0.1:8000     # gunicorn local
    python3 scripts/verificar_servidor.py http://IP --md salida.md   # además guarda Markdown

Termina con código 1 si algún caso no coincide o el servidor no responde.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

NA = "No aplica"

# (n.º, descripción, cuerpo de la petición, esperado)
# esperado = {"estado": 200, "filas": {clave: valor, ...}} o
#            {"estado": 422, "campo": ..., "contiene": "texto del mensaje"}
CASOS = [
    (1, "192.168.1.100/24", {"entrada": "192.168.1.100/24"},
     {"estado": 200, "filas": {"red": "192.168.1.0", "broadcast": "192.168.1.255",
                               "primer_host": "192.168.1.1", "ultimo_host": "192.168.1.254",
                               "total": "256", "hosts": "254", "mascara": "255.255.255.0",
                               "prefijo": "/24", "clase": "C", "uso": "Privada (RFC 1918)"}}),
    (2, "172.16.10.50/30", {"entrada": "172.16.10.50/30"},
     {"estado": 200, "filas": {"red": "172.16.10.48", "broadcast": "172.16.10.51",
                               "primer_host": "172.16.10.49", "ultimo_host": "172.16.10.50",
                               "total": "4", "hosts": "2", "clase": "B",
                               "uso": "Privada (RFC 1918)"}}),
    (3, "10.0.0.0/31", {"entrada": "10.0.0.0/31"},
     {"estado": 200, "filas": {"primer_host": "10.0.0.0", "ultimo_host": "10.0.0.1",
                               "total": "2", "hosts": "2", "clase": "A"},
      "nota": "RFC 3021"}),
    (4, "192.168.1.25/32", {"entrada": "192.168.1.25/32"},
     {"estado": 200, "filas": {"red": "192.168.1.25", "total": "1", "mascara": "255.255.255.255",
                               "clase": "C", "primer_host": NA, "ultimo_host": NA,
                               "broadcast": NA}}),
    (5, "224.0.0.1/24", {"entrada": "224.0.0.1/24"},
     {"estado": 200, "filas": {"red": NA, "broadcast": NA, "primer_host": NA, "ultimo_host": NA,
                               "hosts": NA, "clase": "D (multicast)"}}),
    (6, "240.0.0.1/24", {"entrada": "240.0.0.1/24"},
     {"estado": 200, "filas": {"red": NA, "broadcast": NA, "primer_host": NA, "ultimo_host": NA,
                               "hosts": NA, "clase": "E (reservada)"}}),
    (7, "127.0.0.1/8", {"entrada": "127.0.0.1/8"},
     {"estado": 200, "filas": {"red": "127.0.0.0", "broadcast": "127.255.255.255",
                               "total": "16.777.216", "hosts": "16.777.214", "clase": "A",
                               "uso": "Propósito especial: loopback"}}),
    (8, "169.254.10.20/16", {"entrada": "169.254.10.20/16"},
     {"estado": 200, "filas": {"red": "169.254.0.0", "broadcast": "169.254.255.255",
                               "total": "65.536", "hosts": "65.534", "clase": "B",
                               "uso": "Propósito especial: link-local"}}),
    (9, "192.168.1.300/24", {"entrada": "192.168.1.300/24"},
     {"estado": 422, "campo": "entrada", "contiene": "octeto 4 (300)"}),
    (10, "192.168.1.10/33", {"entrada": "192.168.1.10/33"},
     {"estado": 422, "campo": "entrada", "contiene": "/33"}),
    (11, "192.168.1.10 y 255.0.255.0", {"direccion": "192.168.1.10", "mascara": "255.0.255.0"},
     {"estado": 422, "campo": "mascara", "contiene": "no es contigua"}),
    (12, "192.168.10.25/27", {"entrada": "192.168.10.25/27"},
     {"estado": 200, "filas": {"red": "192.168.10.0", "broadcast": "192.168.10.31",
                               "primer_host": "192.168.10.1", "ultimo_host": "192.168.10.30",
                               "total": "32", "hosts": "30", "mascara": "255.255.255.224",
                               "clase": "C", "uso": "Privada (RFC 1918)"}}),
    ("12b", "192.168.10.25 y 255.255.255.224", {"direccion": "192.168.10.25", "mascara": "255.255.255.224"},
     {"estado": 200, "filas": {"red": "192.168.10.0", "broadcast": "192.168.10.31",
                               "primer_host": "192.168.10.1", "ultimo_host": "192.168.10.30",
                               "total": "32", "hosts": "30", "mascara": "255.255.255.224",
                               "prefijo": "/27", "clase": "C", "uso": "Privada (RFC 1918)"}}),
    (13, "255.255.255.255/32", {"entrada": "255.255.255.255/32"},
     {"estado": 200, "filas": {"red": NA, "broadcast": NA, "primer_host": NA, "ultimo_host": NA,
                               "total": NA, "hosts": NA, "clase": "E (reservada)",
                               "uso": "Propósito especial: broadcast limitado"}}),
    (14, "0.0.0.0/0", {"entrada": "0.0.0.0/0"},
     {"estado": 200, "filas": {"red": "0.0.0.0", "broadcast": "255.255.255.255",
                               "total": "4.294.967.296", "mascara": "0.0.0.0", "prefijo": "/0"}}),
    (15, "192.168.01.10/24", {"entrada": "192.168.01.10/24"},
     {"estado": 422, "campo": "entrada", "contiene": "cuatro octetos"}),
]


def peticion(base, ruta, cuerpo=None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    req = urllib.request.Request(base + ruta, data=datos,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def evaluar(base, cuerpo, esp):
    """Devuelve (coincide, resumen del obtenido)."""
    estado, datos = peticion(base, "/api/calcular", cuerpo)
    if estado != esp["estado"]:
        return False, "HTTP {} (se esperaba {})".format(estado, esp["estado"])
    if estado == 422:
        err = datos["errores"][0]
        ok = err["campo"] == esp["campo"] and esp["contiene"] in err["mensaje"]
        return ok, "HTTP 422, campo {}: {}".format(err["campo"], err["mensaje"])
    filas = {f["clave"]: f["valor"] for f in datos["filas"]}
    faltan = ["{}={!r} (esperado {!r})".format(k, filas.get(k), v)
              for k, v in esp["filas"].items() if filas.get(k) != v]
    if "nota" in esp and esp["nota"] not in json.dumps(datos.get("nota") or {}, ensure_ascii=False):
        faltan.append("nota sin '{}'".format(esp["nota"]))
    resumen = "HTTP 200, {}, {}, {}".format(filas.get("clase"), filas.get("prefijo"),
                                            "red " + str(filas.get("red")))
    return (not faltan), (resumen if not faltan else "; ".join(faltan))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url", help="base de la API, p. ej. http://18.236.163.1")
    ap.add_argument("--md", help="guarda también la tabla en este archivo Markdown")
    a = ap.parse_args()
    base = a.url.rstrip("/")

    try:
        estado, salud = peticion(base, "/api/salud")
    except Exception as e:  # sin conexión, timeout, DNS...
        print("No se pudo llegar a {}: {}".format(base, e))
        return 1
    print("GET /api/salud -> {} {}".format(estado, salud))

    lineas = ["| # | Entrada | Obtenido | OK |", "|---|---|---|---|"]
    fallos = 0
    for n, desc, cuerpo, esp in CASOS:
        try:
            coincide, obtenido = evaluar(base, cuerpo, esp)
        except Exception as e:
            coincide, obtenido = False, "sin respuesta: {}".format(e)
        fallos += 0 if coincide else 1
        print("{:>3}  {:<4} {:<34} {}".format(n, "OK" if coincide else "FAIL", desc, obtenido))
        lineas.append("| {} | `{}` | {} | {} |".format(n, desc, obtenido.replace("|", "/"),
                                                     "Sí" if coincide else "NO"))
    print("\n{} de {} casos coinciden.".format(len(CASOS) - fallos, len(CASOS)))
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write("Servidor: {}\n\n".format(base) + "\n".join(lineas) + "\n")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
