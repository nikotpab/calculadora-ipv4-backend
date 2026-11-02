"""Convierte un Resultado en el JSON del contrato con el frontend.

El frontend solo pinta: aquí se deciden las etiquetas, el formato de los
números y los textos "No aplica…" de cada fila.
"""

from typing import Any, Dict, List, Optional

from calc import mensajes
from calc.ipv4 import (
    ErrorValidacion,
    Resultado,
    binario_punteado,
    calcular,
    decimal_punteado,
    interpretar_cidr,
    interpretar_direccion_mascara,
)

# Filas que el frontend muestra en fuente monoespaciada.
CLAVES_MONO = frozenset(
    ("red", "broadcast", "primer_host", "ultimo_host", "total", "hosts", "mascara", "prefijo")
)


def formatear_miles(numero: int) -> str:
    """16777216 -> "16.777.216" (punto de miles, estilo Colombia)."""
    return "{:,}".format(numero).replace(",", ".")


def respuesta_cidr(entrada: str) -> Dict[str, Any]:
    """Formato A ("192.168.10.25/27"). Lanza ErrorValidacion."""
    return construir_respuesta(calcular(*interpretar_cidr(entrada)))


def respuesta_direccion_mascara(direccion: str, mascara: str) -> Dict[str, Any]:
    """Formato B (dirección y máscara decimal). Lanza ErrorValidacion."""
    return construir_respuesta(calcular(*interpretar_direccion_mascara(direccion, mascara)))


def construir_error(error: ErrorValidacion) -> Dict[str, Any]:
    return {"ok": False, "errores": [{"campo": error.campo, "mensaje": error.mensaje}]}


def construir_respuesta(resultado: Resultado) -> Dict[str, Any]:
    direccion = decimal_punteado(resultado.direccion)
    mascara = decimal_punteado(resultado.mascara)
    return {
        "ok": True,
        "entrada": {
            "direccion": direccion,
            "mascara": mascara,
            "prefijo": resultado.prefijo,
            "texto": mensajes.texto_entrada(direccion, mascara, resultado.prefijo),
        },
        "nota": _nota(resultado.nota),
        "filas": _filas(resultado),
        "binario": {
            "direccion": binario_punteado(resultado.direccion),
            "mascara": binario_punteado(resultado.mascara),
            "red": _o_none(binario_punteado, resultado.bloque),
            "bits_red": resultado.prefijo,
        },
        "datos": {
            "direccion": direccion,
            "mascara": mascara,
            "prefijo": resultado.prefijo,
            "clase": resultado.clase,
            "uso": resultado.uso,
            "red": _o_none(decimal_punteado, resultado.red),
            "broadcast": _o_none(decimal_punteado, resultado.broadcast),
            "primer_host": _o_none(decimal_punteado, resultado.primer_host),
            "ultimo_host": _o_none(decimal_punteado, resultado.ultimo_host),
            "total": resultado.total,
            "hosts": resultado.hosts,
        },
    }


def _o_none(formato, valor: Optional[int]) -> Optional[str]:
    return None if valor is None else formato(valor)


def _nota(codigo: Optional[str]) -> Optional[Dict[str, str]]:
    if codigo is None:
        return None
    titulo, texto = mensajes.NOTAS[codigo]
    return {"titulo": titulo, "texto": texto}


def _textos_no_aplica(resultado: Resultado) -> Dict[str, str]:
    """Textos específicos de /31 y /32; el resto de huecos dice "No aplica"."""
    if resultado.con_subred and resultado.prefijo == 31:
        return {
            "red": mensajes.NO_SE_RESERVA_RFC3021,
            "broadcast": mensajes.NO_APLICA_EN_ENLACE,
        }
    if resultado.con_subred and resultado.prefijo == 32:
        return {"hosts": mensajes.NO_APLICA_RUTA_DE_HOST}
    return {}


def _filas(resultado: Resultado) -> List[Dict[str, Any]]:
    valores = {
        "red": _o_none(decimal_punteado, resultado.red),
        "broadcast": _o_none(decimal_punteado, resultado.broadcast),
        "primer_host": _o_none(decimal_punteado, resultado.primer_host),
        "ultimo_host": _o_none(decimal_punteado, resultado.ultimo_host),
        "total": _o_none(formatear_miles, resultado.total),
        "hosts": _o_none(formatear_miles, resultado.hosts),
        "mascara": decimal_punteado(resultado.mascara),
        "prefijo": "/{}".format(resultado.prefijo),
        "clase": mensajes.TEXTO_CLASE[resultado.clase],
        "uso": mensajes.TEXTO_USO[resultado.uso],
    }
    no_aplica = _textos_no_aplica(resultado)
    filas = []
    for clave, etiqueta in mensajes.ETIQUETAS.items():
        valor = valores[clave]
        aplica = valor is not None
        filas.append({
            "clave": clave,
            "etiqueta": etiqueta,
            "valor": valor if aplica else no_aplica.get(clave, mensajes.NO_APLICA),
            "aplica": aplica,
            "mono": clave in CLAVES_MONO,
        })
    return filas
