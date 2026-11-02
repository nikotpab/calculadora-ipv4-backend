"""Algoritmo de direccionamiento IPv4 con enteros de 32 bits.

Una dirección IPv4 son 32 bits. Aquí se guarda como un ``int`` entre 0 y
2**32 - 1, y todo el cálculo se hace con operaciones de bits:

    máscara   = 32 unos desplazados (32 - prefijo) posiciones a la izquierda
    red       = dirección AND máscara
    broadcast = red OR (NOT máscara)

Los enteros de Python no tienen tamaño fijo ni signo de 32 bits: ``~x`` da un
número negativo y ``x << n`` crece sin límite. Por eso cada NOT y cada
desplazamiento a la izquierda se recorta con ``& MASCARA_32``.

Este módulo no depende de Flask ni del módulo estándar de direcciones IP:
el análisis del texto, el cálculo y la clasificación están hechos a mano.
"""

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from calc import mensajes

BITS = 32
MASCARA_32 = 0xFFFFFFFF  # 32 unos: recorta cualquier resultado a 32 bits
DIGITOS_ASCII = frozenset("0123456789")
# Lo más largo que se acepta es "255.255.255.255/32" (18 caracteres). El
# límite solo evita procesar textos absurdamente largos.
LONGITUD_MAXIMA = 64


class ErrorValidacion(ValueError):
    """Entrada rechazada.

    ``campo`` es el input donde el frontend debe mostrar ``mensaje``:
    "entrada" en el formato dirección/prefijo, "direccion" o "mascara" en el
    formato dirección y máscara.
    """

    def __init__(self, campo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.campo = campo
        self.mensaje = mensaje


# ---------------------------------------------------------------------------
# Conversión entre texto y entero de 32 bits
# ---------------------------------------------------------------------------

def octetos_a_entero(octetos: Sequence[int]) -> int:
    """[192, 168, 1, 100] -> 3232235876 (0xC0A80164).

    Cada octeto entra por la derecha: se desplaza lo acumulado 8 bits a la
    izquierda y se hace OR con el octeto nuevo.
    """
    valor = 0
    for octeto in octetos:
        valor = (valor << 8) | octeto
    return valor


def entero_a_octetos(valor: int) -> List[int]:
    """3232235876 -> [192, 168, 1, 100]. Desplaza y se queda con 8 bits."""
    return [(valor >> desplazamiento) & 0xFF for desplazamiento in (24, 16, 8, 0)]


def decimal_punteado(valor: int) -> str:
    return ".".join(str(octeto) for octeto in entero_a_octetos(valor))


def binario_punteado(valor: int) -> str:
    return ".".join(format(octeto, "08b") for octeto in entero_a_octetos(valor))


# ---------------------------------------------------------------------------
# Máscara y prefijo
# ---------------------------------------------------------------------------

def mascara_desde_prefijo(prefijo: int) -> int:
    """/27 -> 255.255.255.224.

    32 unos desplazados (32 - prefijo) posiciones a la izquierda dejan
    ``prefijo`` unos seguidos de ceros. El AND recorta los bits que se salen
    por la izquierda. Con /0 el desplazamiento es 32 y el resultado es 0.
    """
    return (MASCARA_32 << (BITS - prefijo)) & MASCARA_32


def prefijo_desde_mascara(mascara: int) -> Optional[int]:
    """255.255.255.224 -> 27. Devuelve None si la máscara no es contigua.

    En una máscara contigua los bits de host (NOT máscara) tienen la forma
    0…01…1. Sumarle 1 a ese número produce un solo bit en 1 sin ningún bit
    en común, así que el AND da 0. Si hay un cero entre los unos de la
    máscara, el AND no da 0. Si es contigua, el prefijo es el número de unos.
    """
    bits_de_host = ~mascara & MASCARA_32
    if bits_de_host & (bits_de_host + 1):
        return None
    return bin(mascara).count("1")


# ---------------------------------------------------------------------------
# Lectura y validación del texto de entrada
# ---------------------------------------------------------------------------

def _octeto_bien_escrito(parte: str) -> bool:
    """Solo dígitos ASCII, sin signo ni espacios, y sin ceros a la izquierda.

    ``str.isdigit()`` acepta dígitos Unicode como "²" o "٣", por eso se
    compara contra "0123456789". Los ceros a la izquierda ("01") se rechazan
    porque algunas herramientas los leen en octal.
    """
    if not parte or any(caracter not in DIGITOS_ASCII for caracter in parte):
        return False
    return parte == "0" or parte[0] != "0"


def _leer_octetos(texto: str, campo: str, mensaje_malformado: str) -> List[int]:
    """Convierte "a.b.c.d" en cuatro enteros de 0 a 255.

    Primero se comprueba la forma (cuatro partes numéricas) y después el
    rango, octeto por octeto, para informar del primero que falle.
    """
    partes = texto.split(".")
    if len(partes) != 4 or not all(_octeto_bien_escrito(parte) for parte in partes):
        raise ErrorValidacion(campo, mensaje_malformado)
    for posicion, parte in enumerate(partes, start=1):
        if len(parte) > 3 or int(parte) > 255:
            raise ErrorValidacion(
                campo, mensajes.error_octeto_fuera_de_rango(posicion, parte)
            )
    return [int(parte) for parte in partes]


def _prefijo_sugerido(texto_mascara: str) -> int:
    """Si tras la barra hay una máscara contigua, su prefijo; si no, 24."""
    try:
        mascara = octetos_a_entero(_leer_octetos(texto_mascara, "entrada", ""))
    except ErrorValidacion:
        return 24
    prefijo = prefijo_desde_mascara(mascara)
    return 24 if prefijo is None else prefijo


def _leer_prefijo(texto: str) -> int:
    if texto == "":
        raise ErrorValidacion("entrada", mensajes.ERROR_FALTA_PREFIJO)
    if "." in texto:
        raise ErrorValidacion(
            "entrada", mensajes.error_mascara_en_prefijo(_prefijo_sugerido(texto))
        )
    if any(caracter not in DIGITOS_ASCII for caracter in texto):
        raise ErrorValidacion("entrada", mensajes.ERROR_PREFIJO_NO_NUMERICO)
    if len(texto.lstrip("0")) > 2 or int(texto) > BITS:
        raise ErrorValidacion("entrada", mensajes.error_prefijo_fuera_de_rango(texto))
    return int(texto)


def interpretar_cidr(entrada: str) -> Tuple[int, int]:
    """Formato A: "192.168.10.25/27" -> (dirección como entero, prefijo).

    Valida la dirección antes que el prefijo y lanza ErrorValidacion con
    campo "entrada" ante el primer problema.
    """
    texto = entrada.strip()
    if not texto:
        raise ErrorValidacion("entrada", mensajes.ERROR_DIRECCION_VACIA)
    if len(texto) > LONGITUD_MAXIMA:
        raise ErrorValidacion("entrada", mensajes.ERROR_DIRECCION_MALFORMADA)
    texto_direccion, barra, texto_prefijo = texto.partition("/")
    octetos = _leer_octetos(texto_direccion, "entrada", mensajes.ERROR_DIRECCION_MALFORMADA)
    prefijo = _leer_prefijo(texto_prefijo if barra else "")
    return octetos_a_entero(octetos), prefijo


def interpretar_direccion_mascara(direccion: str, mascara: str) -> Tuple[int, int]:
    """Formato B: ("192.168.10.25", "255.255.255.224") -> (entero, 27).

    Valida la dirección (campo "direccion") antes que la máscara (campo
    "mascara"). La máscara debe ser contigua; se convierte a prefijo.
    """
    texto_direccion = direccion.strip()
    if not texto_direccion:
        raise ErrorValidacion("direccion", mensajes.ERROR_DIRECCION_VACIA)
    if len(texto_direccion) > LONGITUD_MAXIMA:
        raise ErrorValidacion("direccion", mensajes.ERROR_DIRECCION_MALFORMADA)
    ip = octetos_a_entero(
        _leer_octetos(texto_direccion, "direccion", mensajes.ERROR_DIRECCION_MALFORMADA)
    )

    texto_mascara = mascara.strip()
    if not texto_mascara:
        raise ErrorValidacion("mascara", mensajes.ERROR_MASCARA_VACIA)
    if len(texto_mascara) > LONGITUD_MAXIMA:
        raise ErrorValidacion("mascara", mensajes.ERROR_MASCARA_MALFORMADA)
    valor_mascara = octetos_a_entero(
        _leer_octetos(texto_mascara, "mascara", mensajes.ERROR_MASCARA_MALFORMADA)
    )
    prefijo = prefijo_desde_mascara(valor_mascara)
    if prefijo is None:
        raise ErrorValidacion("mascara", mensajes.ERROR_MASCARA_NO_CONTIGUA)
    return ip, prefijo


# ---------------------------------------------------------------------------
# Clase y clasificación de uso
# ---------------------------------------------------------------------------

def clase_de(ip: int) -> str:
    """Clase tradicional por el primer octeto (bits iniciales 0, 10, 110, 1110, 1111)."""
    primer_octeto = ip >> 24
    if primer_octeto <= 127:
        return "A"
    if primer_octeto <= 191:
        return "B"
    if primer_octeto <= 223:
        return "C"
    if primer_octeto <= 239:
        return "D"
    return "E"


# (red, prefijo, código de uso). Fuentes: RFC 1918 para los tres bloques
# privados; RFC 6890 y el registro IANA de propósito especial para el resto;
# RFC 1112 y RFC 5771 para multicast. Los bloques no se solapan, así que el
# orden de la tabla no cambia el resultado.
RANGOS_DE_USO = (
    ((10, 0, 0, 0), 8, "privada"),
    ((172, 16, 0, 0), 12, "privada"),
    ((192, 168, 0, 0), 16, "privada"),
    ((0, 0, 0, 0), 8, "esta_red"),
    ((100, 64, 0, 0), 10, "espacio_compartido"),
    ((127, 0, 0, 0), 8, "loopback"),
    ((169, 254, 0, 0), 16, "link_local"),
    ((192, 0, 0, 0), 24, "asignaciones_ietf"),
    ((192, 0, 2, 0), 24, "test_net_1"),
    ((192, 88, 99, 0), 24, "retransmision_6to4"),
    ((198, 18, 0, 0), 15, "pruebas_rendimiento"),
    ((198, 51, 100, 0), 24, "test_net_2"),
    ((203, 0, 113, 0), 24, "test_net_3"),
    ((224, 0, 0, 0), 4, "multicast"),
    ((240, 0, 0, 0), 4, "reservada"),
)

_RANGOS = tuple(
    (octetos_a_entero(red), mascara_desde_prefijo(prefijo), codigo)
    for red, prefijo, codigo in RANGOS_DE_USO
)


def clasificar_uso(ip: int) -> str:
    """Código de uso de la dirección (ver mensajes.TEXTO_USO).

    0.0.0.0 y 255.255.255.255 se comprueban antes que sus bloques porque
    tienen nombre propio. Una dirección pertenece a un bloque si al aplicar
    la máscara del bloque queda su dirección de red.
    """
    if ip == 0:
        return "no_especificada"
    if ip == MASCARA_32:
        return "broadcast_limitado"
    for red, mascara, codigo in _RANGOS:
        if ip & mascara == red:
            return codigo
    return "publica"


# ---------------------------------------------------------------------------
# Cálculo del bloque
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Resultado:
    """Valores crudos del cálculo. None significa "no aplica"."""

    direccion: int
    prefijo: int
    mascara: int
    clase: str
    uso: str
    con_subred: bool  # False en clase D, clase E, 0.0.0.0 y 255.255.255.255
    bloque: Optional[int]  # dirección AND máscara, para la vista binaria
    red: Optional[int]
    broadcast: Optional[int]
    primer_host: Optional[int]
    ultimo_host: Optional[int]
    total: Optional[int]
    hosts: Optional[int]
    nota: Optional[str]  # código de mensajes.NOTAS


def tiene_calculo_de_subred(ip: int, prefijo: int) -> bool:
    """Las clases D y E (incluida 255.255.255.255) y 0.0.0.0 no son hosts
    unicast: no se calcula subred, sea cual sea el prefijo. Excepción:
    0.0.0.0/0 es la ruta por defecto y se calcula como cualquier /0.
    """
    if ip == 0:
        return prefijo == 0
    return clase_de(ip) in ("A", "B", "C")


def _elegir_nota(ip: int, prefijo: int, clase: str, uso: str, con_subred: bool) -> Optional[str]:
    """Una sola nota por resultado.

    Si la dirección no admite cálculo de subred, la nota explica la
    dirección (multicast, reservada, no especificada o broadcast limitado),
    porque una nota sobre el prefijo contradiría las filas "No aplica".
    En el resto, la prioridad es /31, /32, /0, loopback, link-local.
    """
    if not con_subred:
        if ip == 0:
            return "no_especificada"
        if ip == MASCARA_32:
            return "broadcast_limitado"
        return "multicast" if clase == "D" else "reservada"
    if prefijo == 31:
        return "enlace_31"
    if prefijo == 32:
        return "host_32"
    if prefijo == 0:
        return "prefijo_0"
    if uso in ("loopback", "link_local"):
        return uso
    return None


def calcular(ip: int, prefijo: int) -> Resultado:
    """Calcula el bloque al que pertenece ``ip``/``prefijo``.

    Prefijo <= 30: red y broadcast reservados, hosts = 2^(32-p) - 2.
    Prefijo 31 (RFC 3021): las dos direcciones son hosts, sin red ni broadcast.
    Prefijo 32: una sola dirección; no hay hosts "utilizables" que contar.
    """
    if not 0 <= ip <= MASCARA_32 or not 0 <= prefijo <= BITS:
        raise ValueError("dirección o prefijo fuera de rango")

    mascara = mascara_desde_prefijo(prefijo)
    bits_de_host = ~mascara & MASCARA_32  # NOT máscara, recortado a 32 bits
    primera = ip & mascara                # todos los bits de host a 0
    ultima = primera | bits_de_host       # todos los bits de host a 1

    clase = clase_de(ip)
    uso = clasificar_uso(ip)
    con_subred = tiene_calculo_de_subred(ip, prefijo)

    red = broadcast = primer_host = ultimo_host = total = hosts = None
    if con_subred:
        total = 1 << (BITS - prefijo)  # 2^(32 - prefijo)
        if prefijo == 32:
            red = ip
        elif prefijo == 31:
            primer_host, ultimo_host = primera, ultima
            hosts = 2
        else:
            red, broadcast = primera, ultima
            primer_host, ultimo_host = primera + 1, ultima - 1
            hosts = total - 2

    return Resultado(
        direccion=ip,
        prefijo=prefijo,
        mascara=mascara,
        clase=clase,
        uso=uso,
        con_subred=con_subred,
        bloque=primera if con_subred else None,
        red=red,
        broadcast=broadcast,
        primer_host=primer_host,
        ultimo_host=ultimo_host,
        total=total,
        hosts=hosts,
        nota=_elegir_nota(ip, prefijo, clase, uso, con_subred),
    )
