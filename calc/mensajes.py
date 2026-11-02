"""Textos en español que devuelve la API.

Todo lo que lee el usuario final está aquí, separado del algoritmo, para
revisar la redacción en un solo sitio. Los mensajes de error empiezan por
"Error:", dicen qué pasó y cómo corregirlo, y no usan la palabra "inválido".
"""

# ---------------------------------------------------------------------------
# Errores de validación de la entrada (HTTP 422)
# ---------------------------------------------------------------------------

ERROR_DIRECCION_VACIA = "Error: escribe una dirección IPv4, por ejemplo 192.168.10.25."
ERROR_MASCARA_VACIA = "Error: escribe una máscara decimal, por ejemplo 255.255.255.224."
ERROR_DIRECCION_MALFORMADA = (
    "Error: la dirección debe tener cuatro octetos numéricos separados por puntos, "
    "por ejemplo 192.168.10.25."
)
ERROR_MASCARA_MALFORMADA = (
    "Error: la máscara debe tener cuatro octetos numéricos separados por puntos, "
    "por ejemplo 255.255.255.224."
)
ERROR_FALTA_PREFIJO = (
    "Error: falta el prefijo. Escribe la dirección seguida de /prefijo, "
    "por ejemplo 192.168.10.25/27."
)
ERROR_PREFIJO_NO_NUMERICO = (
    "Error: el prefijo debe ser un número entero entre 0 y 32, por ejemplo /27."
)
ERROR_MASCARA_NO_CONTIGUA = (
    "Error: la máscara no es contigua. Debe tener todos los unos seguidos y luego "
    "todos los ceros, por ejemplo 255.255.255.0."
)


def error_octeto_fuera_de_rango(posicion: int, valor: str) -> str:
    return (
        "Error: el octeto {} ({}) está fuera de rango. "
        "Cada octeto debe estar entre 0 y 255.".format(posicion, valor)
    )


def error_prefijo_fuera_de_rango(valor: str) -> str:
    return "Error: el prefijo /{} está fuera de rango. Debe estar entre 0 y 32.".format(valor)


def error_mascara_en_prefijo(prefijo_sugerido: int) -> str:
    return (
        "Error: en este formato el prefijo va como número. Usa /{}, o pasa la máscara "
        "por separado en el formato dirección y máscara.".format(prefijo_sugerido)
    )


# ---------------------------------------------------------------------------
# Errores de la petición HTTP (400 y otros códigos)
# ---------------------------------------------------------------------------

ERROR_JSON_MAL_FORMADO = (
    'Error: el cuerpo de la petición no es JSON bien formado. '
    'Envía un objeto como {"entrada": "192.168.10.25/27"}.'
)
ERROR_JSON_NO_OBJETO = (
    'Error: el cuerpo de la petición debe ser un objeto JSON, '
    'por ejemplo {"entrada": "192.168.10.25/27"}.'
)
ERROR_FORMATOS_MEZCLADOS = (
    'Error: usa un solo formato: "entrada", o bien "direccion" y "mascara", '
    "pero no los dos a la vez."
)
ERROR_SIN_DATOS = (
    'Error: faltan los datos. Envía "entrada" (por ejemplo 192.168.10.25/27), '
    'o "direccion" y "mascara".'
)
ERROR_RUTA_NO_EXISTE = (
    "Error: la ruta no existe. Usa /api/calcular, /api/casos-de-prueba o /api/salud."
)
ERROR_METODO_NO_PERMITIDO = "Error: esta ruta no admite ese método HTTP."
ERROR_PETICION_DEMASIADO_GRANDE = "Error: la petición es demasiado grande."
ERROR_PETICION_GENERICO = "Error: no se pudo procesar la petición."
ERROR_INTERNO = "Error: fallo interno del servidor. Inténtalo de nuevo."


def error_campo_no_texto(campo: str) -> str:
    return 'Error: el campo "{}" debe ser texto entre comillas.'.format(campo)


# ---------------------------------------------------------------------------
# Tabla de resultados
# ---------------------------------------------------------------------------

# Orden y etiquetas de las 10 filas. El orden de este diccionario es el
# orden en que el frontend pinta la tabla.
ETIQUETAS = {
    "red": "Dirección de red",
    "broadcast": "Broadcast dirigido",
    "primer_host": "Primer host utilizable",
    "ultimo_host": "Último host utilizable",
    "total": "Direcciones en el bloque",
    "hosts": "Hosts utilizables",
    "mascara": "Máscara decimal",
    "prefijo": "Prefijo CIDR",
    "clase": "Clase tradicional",
    "uso": "Clasificación de uso",
}

NO_APLICA = "No aplica"
NO_SE_RESERVA_RFC3021 = "No se reserva (RFC 3021)"
NO_APLICA_EN_ENLACE = "No aplica en este enlace"
NO_APLICA_RUTA_DE_HOST = "No aplica (ruta de host)"

TEXTO_CLASE = {
    "A": "A",
    "B": "B",
    "C": "C",
    "D": "D (multicast)",
    "E": "E (reservada)",
}

TEXTO_USO = {
    "privada": "Privada (RFC 1918)",
    "publica": "Pública global",
    "no_especificada": "Propósito especial: no especificada",
    "broadcast_limitado": "Propósito especial: broadcast limitado",
    "esta_red": "Propósito especial: esta red",
    "espacio_compartido": "Propósito especial: espacio compartido (CGNAT)",
    "loopback": "Propósito especial: loopback",
    "link_local": "Propósito especial: link-local",
    "asignaciones_ietf": "Propósito especial: asignaciones IETF",
    "test_net_1": "Propósito especial: documentación (TEST-NET-1)",
    "retransmision_6to4": "Propósito especial: retransmisión 6to4 (obsoleto)",
    "pruebas_rendimiento": "Propósito especial: pruebas de rendimiento",
    "test_net_2": "Propósito especial: documentación (TEST-NET-2)",
    "test_net_3": "Propósito especial: documentación (TEST-NET-3)",
    "multicast": "Propósito especial: multicast",
    "reservada": "Propósito especial: reservada (240.0.0.0/4)",
}

# Notas: código -> (título, texto). El título es una frase corta terminada
# en punto (el frontend la pone en negrita); el texto es la continuación.
NOTAS = {
    "enlace_31": (
        "Enlace punto a punto (RFC 3021).",
        "Con prefijo /31 las dos direcciones del bloque se asignan a los extremos "
        "del enlace. No se reservan dirección de red ni broadcast dirigido.",
    ),
    "host_32": (
        "Dirección individual (/32).",
        "Identifica un solo host o una ruta de host; no se aplica la fórmula de "
        "hosts útiles de una subred.",
    ),
    "prefijo_0": (
        "Prefijo /0.",
        "Se admite; abarca todo el espacio IPv4 (ruta por defecto).",
    ),
    "multicast": (
        "Dirección multicast (clase D).",
        "El rango 224.0.0.0 – 239.255.255.255 identifica grupos, no hosts. "
        "No se calculan red, broadcast ni hosts utilizables.",
    ),
    "reservada": (
        "Dirección reservada (clase E).",
        "El rango 240.0.0.0 – 255.255.255.254 es de uso especial; no se trata "
        "como host unicast.",
    ),
    "no_especificada": (
        "Dirección no especificada (0.0.0.0).",
        "No identifica un host concreto; se usa cuando aún no se tiene dirección. "
        "No se calculan red, broadcast ni hosts utilizables.",
    ),
    "broadcast_limitado": (
        "Broadcast limitado (255.255.255.255).",
        "Se entrega a todos los equipos del enlace local y nunca se enruta. "
        "No se calculan red, broadcast ni hosts utilizables.",
    ),
    "loopback": (
        "Dirección de loopback (127.0.0.0/8).",
        "Identifica al propio equipo y no sale a la red.",
    ),
    "link_local": (
        "Dirección link-local (169.254.0.0/16).",
        "Solo es válida dentro del enlace local y no se enruta.",
    ),
}


def texto_entrada(direccion: str, mascara: str, prefijo: int) -> str:
    return "{} · máscara {} · /{}".format(direccion, mascara, prefijo)
