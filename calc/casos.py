"""Casos mínimos de prueba del enunciado, con la etiqueta corta que muestra el frontend."""

CASOS_DE_PRUEBA = (
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
)
