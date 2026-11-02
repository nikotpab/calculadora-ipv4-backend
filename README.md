# Calculadora IPv4: backend

API JSON en Flask de la calculadora web de direccionamiento IPv4 (Redes de
Datos I, Universidad El Bosque, 2026-II). A partir de una dirección con
prefijo (`192.168.10.25/27`) o de una dirección y una máscara decimal
(`192.168.10.25` + `255.255.255.224`) devuelve la tabla de resultados ya
redactada en español: red, broadcast dirigido, rango de hosts, totales,
máscara, prefijo, clase y clasificación de uso, más la vista binaria.

El frontend (HTML + CSS) está en otro repositorio; en producción Nginx sirve
los dos desde el mismo origen.

## Dependencias

| | Versión | Para qué |
|---|---|---|
| Python | 3.9 (el de Rocky Linux 9); probado también con 3.14 | |
| Flask | 3.1.3 | API |
| gunicorn | 23.0.0 | servidor WSGI en producción |
| pytest | 8.4.2 | pruebas (`requirements-dev.txt`) |

`requirements.txt` fija también las dependencias transitivas. No se usa
base de datos, autenticación ni Docker. El cálculo (`calc/`) solo usa la
biblioteca estándar y no importa Flask ni `ipaddress`.

## Estructura

```
.
├── app.py                    API Flask: rutas, lectura de la petición, códigos HTTP
├── calc/                     cálculo, sin Flask
│   ├── ipv4.py               validación del texto, algoritmo con bits, clase y uso
│   ├── respuesta.py          arma el JSON del contrato (filas, binario, datos, nota)
│   ├── mensajes.py           todos los textos en español (errores, etiquetas, notas)
│   └── casos.py              los 11 casos mínimos del enunciado
├── tests/
│   ├── test_ipv4.py          algoritmo, comparación con ipaddress, clasificación, validación, límites
│   ├── test_casos_minimos.py los 11 casos, campo por campo, y formas A = B
│   └── test_api.py           códigos HTTP, forma exacta del JSON, GET = POST
├── scripts/
│   ├── tabla_pruebas.py      genera la tabla de pruebas del informe (Markdown)
│   └── servidor_local.py     desarrollo: frontend + API en el mismo origen, como Nginx
├── deploy/
│   ├── calculadora-ipv4.service   unidad systemd de gunicorn
│   └── nginx/calculadora-ipv4.conf
├── requirements.txt
├── requirements-dev.txt
└── pytest.ini
```

Respecto a la estructura sugerida se añadieron dos módulos: `calc/respuesta.py`
separa la presentación (filas, formato de miles, textos "No aplica…") del
algoritmo, para que `ipv4.py` contenga solo bits y validación; y
`calc/casos.py` guarda los casos de prueba en un solo sitio, porque los usan
la API, las pruebas y el script. La API cabe en un solo `app.py` con una
fábrica `create_app()`.

## Instalación y ejecución local

```bash
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

flask --app app run                    # desarrollo: http://127.0.0.1:5000
gunicorn --bind 127.0.0.1:8000 app:app # como en producción (Linux/macOS)
```

### Con el frontend

El frontend llama a `/api/…` en su mismo origen (sin CORS). Para probarlo en
local, con el repositorio `calculadora-ipv4-frontend` clonado al lado de este:

```bash
python scripts/servidor_local.py       # http://127.0.0.1:8080
python scripts/servidor_local.py --frontend /ruta/a/calculadora-ipv4-frontend/app --puerto 9000
```

Sirve los archivos de `app/` del frontend y deja `/api/` a Flask, igual que
Nginx en producción. Solo para desarrollo.

## Pruebas

```bash
python -m pytest                                        # 280 pruebas
python scripts/tabla_pruebas.py                         # imprime la tabla en Markdown
python scripts/tabla_pruebas.py --salida tabla-pruebas.md
```

Las pruebas incluyen: los 11 casos campo por campo; la equivalencia exacta
entre los formatos A y B y entre GET y POST; una comparación aleatoria de
3.000 pares dirección/prefijo unicast (semilla fija) contra
`ipaddress.ip_network(..., strict=False)`; los 33 prefijos contra sus
máscaras; la trampa de `is_private` (127.0.0.1, 169.254.1.1 y 240.0.0.1 no
son privadas) y los límites de 172.16.0.0/12; un mensaje por cada tipo de
error; los casos límite (0.0.0.0/0, /0, 255.255.255.255, 0.0.0.0/8…); y
la forma exacta del JSON de la API.

`tabla_pruebas.py` compara cada caso con un resultado esperado escrito a
mano y escribe la tabla "entrada | resultado esperado | resultado obtenido |
¿coincide?". Sale con código 1 si algún caso no coincide.

## Contrato de la API

| Método y ruta | Respuesta |
|---|---|
| `POST /api/calcular` | cálculo; cuerpo JSON |
| `GET /api/calcular?entrada=…` o `?direccion=…&mascara=…` | lo mismo, para probar con curl o el navegador |
| `GET /api/casos-de-prueba` | lista de los 11 casos con su etiqueta corta |
| `GET /api/salud` | `{"ok": true}` |

### Entrada

Dos formas equivalentes:

```json
{"entrada": "192.168.10.25/27"}
{"direccion": "192.168.10.25", "mascara": "255.255.255.224"}
```

- Se recortan los espacios al inicio y al final de cada campo.
- Si llegan `entrada` y también `direccion` o `mascara`: **400**.
- En la forma B, si falta uno de los dos campos se trata como vacío (**422**
  con el mensaje de ese campo).
- Se ignora la cabecera `Content-Type`: el cuerpo se lee siempre como JSON.
  Tamaño máximo: 4 KB.

### Respuesta correcta (200)

```json
{
  "ok": true,
  "entrada": {"direccion": "192.168.1.100", "mascara": "255.255.255.0", "prefijo": 24,
              "texto": "192.168.1.100 · máscara 255.255.255.0 · /24"},
  "nota": null,
  "filas": [
    {"clave": "red", "etiqueta": "Dirección de red", "valor": "192.168.1.0", "aplica": true, "mono": true},
    {"clave": "broadcast", "etiqueta": "Broadcast dirigido", "valor": "192.168.1.255", "aplica": true, "mono": true},
    {"clave": "primer_host", "etiqueta": "Primer host utilizable", "valor": "192.168.1.1", "aplica": true, "mono": true},
    {"clave": "ultimo_host", "etiqueta": "Último host utilizable", "valor": "192.168.1.254", "aplica": true, "mono": true},
    {"clave": "total", "etiqueta": "Direcciones en el bloque", "valor": "256", "aplica": true, "mono": true},
    {"clave": "hosts", "etiqueta": "Hosts utilizables", "valor": "254", "aplica": true, "mono": true},
    {"clave": "mascara", "etiqueta": "Máscara decimal", "valor": "255.255.255.0", "aplica": true, "mono": true},
    {"clave": "prefijo", "etiqueta": "Prefijo CIDR", "valor": "/24", "aplica": true, "mono": true},
    {"clave": "clase", "etiqueta": "Clase tradicional", "valor": "C", "aplica": true, "mono": false},
    {"clave": "uso", "etiqueta": "Clasificación de uso", "valor": "Privada (RFC 1918)", "aplica": true, "mono": false}
  ],
  "binario": {"direccion": "11000000.10101000.00000001.01100100",
              "mascara": "11111111.11111111.11111111.00000000",
              "red": "11000000.10101000.00000001.00000000", "bits_red": 24},
  "datos": {"direccion": "192.168.1.100", "mascara": "255.255.255.0", "prefijo": 24,
            "clase": "C", "uso": "privada", "red": "192.168.1.0", "broadcast": "192.168.1.255",
            "primer_host": "192.168.1.1", "ultimo_host": "192.168.1.254", "total": 256, "hosts": 254}
}
```

- `filas`: siempre 10, en este orden. `valor` es texto listo para mostrar
  (miles con punto: `1.024`, `16.777.216`; prefijo como `/24`). `aplica` es
  `false` cuando el valor es un "No aplica…". `mono` es `true` salvo en
  `clase` y `uso`.
- `datos`: valores crudos. `total` y `hosts` son enteros. Los campos `red`,
  `broadcast`, `primer_host`, `ultimo_host`, `total` y `hosts` valen `null`
  exactamente cuando su fila tiene `aplica: false`.
  - `clase`: `"A"` … `"E"`.
  - `uso`: `privada`, `publica`, `no_especificada`, `broadcast_limitado`,
    `esta_red`, `espacio_compartido`, `loopback`, `link_local`,
    `asignaciones_ietf`, `test_net_1`, `retransmision_6to4`,
    `pruebas_rendimiento`, `test_net_2`, `test_net_3`, `multicast`, `reservada`.
- `binario.red`: `null` en clase D, clase E, 0.0.0.0 (salvo /0) y
  255.255.255.255. `bits_red` es el prefijo.
- `nota`: `null` o `{"titulo": "…", "texto": "…"}`.
- La respuesta es idéntica byte a byte con la forma A o la forma B, y por
  GET o por POST.

Valores de las filas en los casos especiales:

| Caso | red | broadcast | primer / último host | total | hosts |
|---|---|---|---|---|---|
| /31 | No se reserva (RFC 3021) | No aplica en este enlace | red, red + 1 | 2 | 2 |
| /32 | la propia dirección | No aplica | No aplica | 1 | No aplica (ruta de host) |
| D, E, 0.0.0.0, 255.255.255.255 | No aplica | No aplica | No aplica | No aplica | No aplica |

### Errores

Error de validación, **422**. Un solo error: el primero, mirando la
dirección antes que la máscara o el prefijo. `campo` dice en qué input
mostrarlo: `entrada` en la forma A; `direccion` o `mascara` en la forma B.

```json
{"ok": false, "errores": [{"campo": "mascara", "mensaje": "Error: la máscara no es contigua. Debe tener todos los unos seguidos y luego todos los ceros, por ejemplo 255.255.255.0."}]}
```

| Caso | Mensaje |
|---|---|
| Campo vacío | `Error: escribe una dirección IPv4, por ejemplo 192.168.10.25.` / `Error: escribe una máscara decimal, por ejemplo 255.255.255.224.` |
| Dirección malformada (no son 4 octetos numéricos ASCII, ceros a la izquierda, `0x…`, dígitos Unicode) | `Error: la dirección debe tener cuatro octetos numéricos separados por puntos, por ejemplo 192.168.10.25.` |
| Octeto fuera de rango | `Error: el octeto 4 (300) está fuera de rango. Cada octeto debe estar entre 0 y 255.` |
| Falta el prefijo (`192.168.1.10`, `192.168.1.10/`) | `Error: falta el prefijo. Escribe la dirección seguida de /prefijo, por ejemplo 192.168.10.25/27.` |
| Prefijo no numérico (`/abc`, `/-1`, `/+8`) | `Error: el prefijo debe ser un número entero entre 0 y 32, por ejemplo /27.` |
| Prefijo fuera de rango | `Error: el prefijo /33 está fuera de rango. Debe estar entre 0 y 32.` |
| Máscara tras la barra (`192.168.1.10/255.255.255.0`) | `Error: en este formato el prefijo va como número. Usa /24, o pasa la máscara por separado en el formato dirección y máscara.` |
| Máscara malformada | `Error: la máscara debe tener cuatro octetos numéricos separados por puntos, por ejemplo 255.255.255.224.` |
| Máscara no contigua | `Error: la máscara no es contigua. Debe tener todos los unos seguidos y luego todos los ceros, por ejemplo 255.255.255.0.` |

Errores de la petición (el usuario no los provoca escribiendo; indican un
fallo del cliente):

| Código | `campo` | Cuándo |
|---|---|---|
| 400 | `cuerpo` | JSON mal formado, o el JSON no es un objeto |
| 400 | `peticion` | formas A y B a la vez, ningún campo, o un campo que no es texto |
| 404 / 405 / 413 / 500 | `peticion` | ruta inexistente, método no permitido, cuerpo > 4 KB, fallo interno |

Todas las respuestas de error tienen la forma `{"ok": false, "errores": [...]}`.

## Ejemplos con curl

```bash
curl -s http://127.0.0.1:5000/api/salud

curl -s -X POST -H 'Content-Type: application/json' \
     -d '{"entrada": "192.168.10.25/27"}' http://127.0.0.1:5000/api/calcular

curl -s -X POST -H 'Content-Type: application/json' \
     -d '{"direccion": "192.168.10.25", "mascara": "255.255.255.224"}' \
     http://127.0.0.1:5000/api/calcular

curl -s "http://127.0.0.1:5000/api/calcular?entrada=10.0.0.0/31"

# --data-urlencode codifica caracteres como "+" (en una URL, "+" es un espacio)
curl -s -G --data-urlencode "entrada=192.168.1.10/+8" http://127.0.0.1:5000/api/calcular

curl -s http://127.0.0.1:5000/api/casos-de-prueba
```

## Datos de prueba (casos mínimos del enunciado)

| Entrada | Resultado esperado |
|---|---|
| 192.168.1.100/24 | Clase C, privada. Red 192.168.1.0, broadcast 192.168.1.255, hosts .1 a .254, total 256, 254 hosts |
| 172.16.10.50/30 | Clase B, privada. Red 172.16.10.48, broadcast 172.16.10.51, hosts .49 a .50, total 4, 2 hosts |
| 10.0.0.0/31 | Clase A, privada. RFC 3021: hosts 10.0.0.0 y 10.0.0.1, total 2, 2 hosts, sin red ni broadcast |
| 192.168.1.25/32 | Clase C, privada. Red 192.168.1.25, total 1, hosts "No aplica (ruta de host)" |
| 224.0.0.1/24 | D (multicast), sin cálculo de subred |
| 240.0.0.1/24 | E (reservada), sin cálculo de subred |
| 127.0.0.1/8 | Clase A, loopback. Red 127.0.0.0, broadcast 127.255.255.255, 16.777.214 hosts |
| 169.254.10.20/16 | Clase B, link-local. Red 169.254.0.0, broadcast 169.254.255.255, 65.534 hosts |
| 192.168.1.300/24 | 422: octeto 4 (300) fuera de rango |
| 192.168.1.10/33 | 422: prefijo /33 fuera de rango |
| 192.168.1.10 + 255.0.255.0 | 422 (campo `mascara`): máscara no contigua |

La tabla completa, con 23 casos adicionales y los resultados obtenidos, la
genera `python scripts/tabla_pruebas.py`.

## Despliegue

Rocky Linux 9 con gunicorn (systemd, 127.0.0.1:8000) detrás de Nginx en el
puerto 80, firewalld y SELinux. Los archivos de configuración están en
`deploy/`; el procedimiento paso a paso está en el documento de despliegue
(`DESPLIEGUE.md`), que se entrega aparte con el resto de la documentación.

## Decisiones de diseño

Las que no vienen del enunciado están explicadas en el documento de casos
especiales (`casos-especiales.md`, en la documentación aparte). En resumen:

- **/0** se admite y abarca todo el espacio IPv4. **0.0.0.0/0** se calcula
  como cualquier /0 (ruta por defecto), aunque 0.0.0.0 con otro prefijo no
  tiene cálculo de subred.
- **Prioridad de notas:** si la dirección no tiene cálculo de subred
  (D, E, 0.0.0.0, 255.255.255.255), su nota gana a la del prefijo; si no,
  /31, /32, /0, loopback, link-local.
- El prefijo acepta ceros a la izquierda (`/024` = 24), igual que
  `ipaddress`; en los octetos se rechazan por la ambigüedad octal.
- Si se escribe una máscara tras la barra, el mensaje sugiere el prefijo
  equivalente cuando la máscara es contigua (`/255.255.0.0` → "Usa /16");
  si no, sugiere /24.
- Textos de más de 64 caracteres se rechazan como malformados.
