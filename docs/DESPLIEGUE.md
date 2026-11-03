# Despliegue en Rocky Linux 9 (Nginx + gunicorn, puerto 80)

Procedimiento reproducible, comando por comando, para publicar la API (y,
cuando se copie, el frontend estático) en un servidor Rocky Linux 9.

```
equipo autorizado ──HTTP :80──▶ Nginx ─┬─ /api/*  ──▶ gunicorn 127.0.0.1:8000 (Flask, systemd)
                                       └─ /*      ──▶ /var/www/calculadora-ipv4 (frontend)
```

## Estado de verificación

> Este procedimiento se redactó en un equipo macOS y después se ejecutó en una
> instancia EC2 con **Rocky Linux 9.8** (región us-west-2, IP pública
> 18.236.163.1). Cada fila dice qué evidencia hay; lo que no tiene captura ni
> salida guardada sigue marcado **NO VERIFICADO**.

| Qué | Estado |
|---|---|
| Pruebas automáticas (`pytest`, 280 pruebas) con Python 3.9.6 y 3.14 | VERIFICADO en macOS |
| Dependencias con wheel para CPython 3.9 en Linux x86_64 y aarch64 (`pip download --only-binary=:all:`) | VERIFICADO |
| Sistema operativo Rocky Linux 9.8 (`cat /etc/os-release`) | VERIFICADO en el servidor (captura, informe fig. 3) |
| `calculadora-ipv4.service` y `nginx.service` activos, 0 unidades fallidas (`systemctl status`) | VERIFICADO en el servidor (informe fig. 5) |
| Puerto 80 en `0.0.0.0` y `[::]`; 8000 solo en `127.0.0.1` (`ss -tlnp`) | VERIFICADO en el servidor (informe fig. 6) |
| firewalld con el servicio `http` (`firewall-cmd --list-services`) | VERIFICADO en el servidor (informe fig. 7) |
| Grupo de seguridad de AWS con TCP 22 y TCP 80 | VERIFICADO (informe fig. 4) |
| Acceso desde otro equipo: `curl http://18.236.163.1/api/salud` desde un MacBook y la interfaz en el navegador (casos 1, 3, 5 y 11) | VERIFICADO (informe figs. 8 y 10 a 13) |
| Los 15 casos de la tabla de pruebas, ejecutados contra el servidor desde otro equipo con `python3 scripts/verificar_servidor.py http://18.236.163.1`: 16 de 16 coinciden | VERIFICADO (informe fig. 9) |
| `nginx -t`, booleano SELinux `httpd_can_network_connect`, reinicio automático tras `kill`, instalación sin Internet con wheels | NO VERIFICADO (sin captura) |

## Datos que necesitas

| Variable | Ejemplo | Cómo obtenerla |
|---|---|---|
| IP del servidor | `192.168.56.20` | en el servidor: `ip -4 addr` o `hostname -I` |
| IP del equipo autorizado | `192.168.56.1` | en ese equipo: `ip -4 addr`, `ifconfig` o `ipconfig` |
| Arquitectura | `x86_64` o `aarch64` | `uname -m` (una VM en un Mac con Apple Silicon suele ser `aarch64`) |

Todos los comandos se ejecutan en el servidor con un usuario que tenga `sudo`,
salvo los del paso 6.2, que se ejecutan en el equipo autorizado.

---

## 1. Instalación

*Estado: NO VERIFICADO.*

### 1.1 Paquetes del sistema

```bash
sudo dnf -y install python3 python3-pip nginx policycoreutils-python-utils
python3 --version          # Rocky Linux 9 trae Python 3.9.x
nginx -v
```

`policycoreutils-python-utils` aporta `semanage`, útil para diagnosticar
SELinux (paso 5). `curl`, `ss` (paquete `iproute`) y `ausearch` (paquete
`audit`) vienen en la instalación base; si faltan:
`sudo dnf -y install curl iproute audit`.

### 1.2 Usuario del servicio (sin shell)

```bash
sudo useradd --system --no-create-home --home-dir /opt/calculadora-ipv4-api \
     --shell /sbin/nologin calculadora
id calculadora
```

### 1.3 Copiar el código a /opt/calculadora-ipv4-api

Desde el equipo de desarrollo, sube la carpeta del backend al servidor (o el
`.zip` y descomprímelo con `unzip`):

```bash
# En el equipo de desarrollo:
scp -r calculadora-ipv4-backend usuario@IP_DEL_SERVIDOR:~/
```

En el servidor:

```bash
cd ~/calculadora-ipv4-backend
sudo mkdir -p /opt/calculadora-ipv4-api
sudo cp -r app.py calc requirements.txt /opt/calculadora-ipv4-api/
```

Se usa `cp` y no `mv`: `cp` crea los archivos con la etiqueta SELinux del
destino; `mv` conservaría la etiqueta de `/home` y systemd no podría
ejecutarlos.

### 1.4 Entorno virtual y dependencias

```bash
sudo python3 -m venv /opt/calculadora-ipv4-api/venv
sudo /opt/calculadora-ipv4-api/venv/bin/pip install -r /opt/calculadora-ipv4-api/requirements.txt
/opt/calculadora-ipv4-api/venv/bin/gunicorn --version     # gunicorn (version 23.0.0)
```

**Servidor sin Internet.** En un equipo con Internet, descarga las wheels
para la arquitectura del servidor (este paso sí se probó en macOS) y cópialas
al servidor junto con el código:

```bash
pip download --only-binary=:all: --platform manylinux2014_x86_64 \
    --python-version 3.9 --implementation cp -r requirements.txt -d wheels
# para aarch64: --platform manylinux2014_aarch64
```

En el servidor (NO VERIFICADO):

```bash
sudo /opt/calculadora-ipv4-api/venv/bin/pip install --no-index \
     --find-links ~/calculadora-ipv4-backend/wheels -r /opt/calculadora-ipv4-api/requirements.txt
```

### 1.5 Permisos y etiquetas

El código pertenece a root y el servicio solo puede leerlo:

```bash
sudo chown -R root:calculadora /opt/calculadora-ipv4-api
sudo chmod -R u=rwX,g=rX,o= /opt/calculadora-ipv4-api
sudo restorecon -Rv /opt/calculadora-ipv4-api
```

### 1.6 (Opcional) Prueba manual antes de systemd

```bash
sudo -u calculadora /opt/calculadora-ipv4-api/venv/bin/gunicorn \
     --chdir /opt/calculadora-ipv4-api --bind 127.0.0.1:8000 app:app
# En otra terminal del servidor:
curl -s http://127.0.0.1:8000/api/salud      # {"ok":true}
# Ctrl+C para pararlo.
```

### 1.7 (Opcional) Pruebas automáticas en el propio servidor

Ejecutarlas en Rocky confirma el cálculo con el Python 3.9 del servidor. Se
usa un entorno aparte para no instalar pytest en el de producción:

```bash
cd ~/calculadora-ipv4-backend
python3 -m venv ~/venv-pruebas
~/venv-pruebas/bin/pip install -r requirements-dev.txt
~/venv-pruebas/bin/python -m pytest
~/venv-pruebas/bin/python scripts/tabla_pruebas.py --salida ~/tabla-pruebas.md
```

---

## 2. gunicorn como servicio systemd

*Estado: NO VERIFICADO.*

El archivo `deploy/calculadora-ipv4.service` del repositorio del backend arranca gunicorn con 2 workers,
escuchando **solo** en `127.0.0.1:8000` (no es accesible desde fuera; solo
Nginx habla con él), con `Restart=always` para reiniciarlo si se cae, y con
los logs hacia journald.

```bash
cd ~/calculadora-ipv4-backend
sudo cp deploy/calculadora-ipv4.service /etc/systemd/system/
sudo restorecon -v /etc/systemd/system/calculadora-ipv4.service
sudo systemctl daemon-reload
sudo systemctl enable --now calculadora-ipv4
systemctl status calculadora-ipv4 --no-pager
curl -s http://127.0.0.1:8000/api/salud      # {"ok":true}
```

Comprobar el reinicio automático:

```bash
sudo systemctl kill --signal=SIGKILL calculadora-ipv4
sleep 5
systemctl is-active calculadora-ipv4          # active
```

---

## 3. Nginx en el puerto 80

*Estado: NO VERIFICADO (no había Nginx en el equipo de desarrollo; `nginx -t`
no se pudo ejecutar).*

`deploy/nginx/calculadora-ipv4.conf` (en el repositorio del backend):

- `listen 80 default_server`: atiende las peticiones que llegan por IP.
- `location /api/` → `proxy_pass` a gunicorn (`127.0.0.1:8000`).
- `location /` → archivos estáticos de `/var/www/calculadora-ipv4`. Mientras
  no se copie el frontend, `/` responde 404.
- Frontend y API en el mismo origen: no hace falta CORS.

```bash
cd ~/calculadora-ipv4-backend
sudo cp deploy/nginx/calculadora-ipv4.conf /etc/nginx/conf.d/
sudo restorecon -v /etc/nginx/conf.d/calculadora-ipv4.conf

# Carpeta del frontend (vacía por ahora)
sudo mkdir -p /var/www/calculadora-ipv4
sudo chmod 755 /var/www/calculadora-ipv4

sudo nginx -t
sudo systemctl enable --now nginx
```

**Si `nginx -t` dice `a duplicate default server for 0.0.0.0:80`**, el
`server` de ejemplo de `/etc/nginx/nginx.conf` también se declara
`default_server`. Quítale esa marca (se guarda copia):

```bash
grep -n "default_server" /etc/nginx/nginx.conf
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.orig
sudo sed -i 's/ default_server//' /etc/nginx/nginx.conf
sudo nginx -t && sudo systemctl reload nginx
```

**Si `nginx -t` falla en `listen [::]:80`** (IPv6 deshabilitado en el
servidor), borra esa línea de `/etc/nginx/conf.d/calculadora-ipv4.conf`.

### 3.1 Copiar el frontend (cuando esté listo)

```bash
sudo cp -r ~/calculadora-ipv4-frontend/. /var/www/calculadora-ipv4/
sudo chown -R root:root /var/www/calculadora-ipv4
sudo chmod -R u=rwX,go=rX /var/www/calculadora-ipv4
sudo restorecon -Rv /var/www/calculadora-ipv4
```

El `fetch` del frontend debe usar la ruta relativa `/api/calcular` (mismo
origen), no `http://127.0.0.1:8000`.

---

## 4. firewalld

*Estado: NO VERIFICADO.*

```bash
sudo systemctl enable --now firewalld
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
sudo firewall-cmd --list-services          # debe incluir http
```

El puerto 8000 **no** se abre: gunicorn solo escucha en 127.0.0.1.

### 4.1 (Opcional) Permitir el puerto 80 solo al equipo autorizado

En lugar de abrir HTTP a toda la red, se puede usar una regla enriquecida
(*rich rule*) que acepte el puerto 80 solo desde la IP del equipo autorizado
(sustituye `192.168.56.1`):

```bash
sudo firewall-cmd --permanent --remove-service=http
sudo firewall-cmd --permanent \
     --add-rich-rule='rule family="ipv4" source address="192.168.56.1/32" service name="http" accept'
sudo firewall-cmd --reload
sudo firewall-cmd --list-rich-rules
```

Con esta regla, cualquier otro equipo recibirá un rechazo o un tiempo de
espera agotado al conectar al puerto 80. Para deshacerla, cambia
`--add-rich-rule` por `--remove-rich-rule` (misma regla) y vuelve a añadir
el servicio `http`.

---

## 5. SELinux

*Estado: NO VERIFICADO.*

Rocky Linux 9 arranca con SELinux en modo `Enforcing`. Hay que hacer dos
ajustes (no desactivar SELinux):

1. **Nginx → gunicorn.** Nginx se ejecuta en el dominio `httpd_t`, que por
   defecto no puede abrir conexiones de red salientes hacia puertos que no
   sean de web. El puerto 8000 no lo es, así que sin este ajuste Nginx
   responde **502 Bad Gateway** y el log de error muestra
   `(13: Permission denied) while connecting to upstream`. El booleano
   `httpd_can_network_connect` lo permite (`-P` lo hace permanente):

   ```bash
   getenforce                                     # Enforcing
   sudo setsebool -P httpd_can_network_connect 1
   getsebool httpd_can_network_connect            # httpd_can_network_connect --> on
   ```

2. **Archivos estáticos.** Nginx solo puede leer archivos con la etiqueta
   `httpd_sys_content_t`. `/var/www` ya la tiene por defecto, pero los
   archivos movidos (`mv`) desde `/home` conservan `user_home_t` y Nginx
   responde **403 Forbidden**. `restorecon` reaplica la etiqueta correcta:

   ```bash
   sudo restorecon -Rv /var/www/calculadora-ipv4
   ls -Zd /var/www/calculadora-ipv4               # ...:httpd_sys_content_t:...
   ```

Una alternativa más restrictiva que el booleano sería etiquetar solo el
puerto 8000 como puerto web con `semanage port`; aquí se usa el booleano por
ser el ajuste estándar y más fácil de explicar.

---

## 6. Verificación

*Estado: NO VERIFICADO en Rocky. Los mismos curl se ejecutaron en macOS contra
gunicorn directo (sin Nginx): 8 respuestas 200 y 3 respuestas 422, como se
espera.*

### 6.1 En el servidor

```bash
systemctl is-active calculadora-ipv4 nginx firewalld   # active ×3
sudo ss -tlnp | grep -E ':80 |:8000 '
#   0.0.0.0:80       ... nginx
#   127.0.0.1:8000   ... gunicorn      ← solo localhost

curl -i http://127.0.0.1/api/salud                   # 200 y {"ok":true}, a través de Nginx
curl -s -X POST -H 'Content-Type: application/json' \
     -d '{"entrada": "192.168.1.100/24"}' http://127.0.0.1/api/calcular
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/   # 404 hasta copiar el frontend
```

### 6.2 Desde el equipo autorizado (otro equipo de la red)

Linux o macOS (sustituye la IP):

```bash
SERVIDOR=192.168.56.20
curl -i http://$SERVIDOR/api/salud
curl -s http://$SERVIDOR/api/casos-de-prueba

# Los 11 casos mínimos: deben salir 8 × 200 y 3 × 422
for e in 192.168.1.100/24 172.16.10.50/30 10.0.0.0/31 192.168.1.25/32 224.0.0.1/24 \
         240.0.0.1/24 127.0.0.1/8 169.254.10.20/16 192.168.1.300/24 192.168.1.10/33; do
  curl -s -o /dev/null -w "%{http_code}  $e\n" -G --data-urlencode "entrada=$e" \
       http://$SERVIDOR/api/calcular
done
curl -s -o /dev/null -w "%{http_code}  192.168.1.10 + 255.0.255.0\n" -G \
     --data-urlencode "direccion=192.168.1.10" --data-urlencode "mascara=255.0.255.0" \
     http://$SERVIDOR/api/calcular

# Respuesta completa de un caso, por POST
curl -s -X POST -H 'Content-Type: application/json' \
     -d '{"entrada": "10.0.0.0/31"}' http://$SERVIDOR/api/calcular
```

Windows (PowerShell; `curl.exe` evita el alias de `Invoke-WebRequest`):

```powershell
curl.exe -i http://192.168.56.20/api/salud
curl.exe "http://192.168.56.20/api/calcular?entrada=192.168.1.100/24"
curl.exe "http://192.168.56.20/api/calcular?direccion=192.168.1.10&mascara=255.0.255.0"
Invoke-RestMethod -Method Post -Uri http://192.168.56.20/api/calcular `
  -ContentType 'application/json' -Body '{"entrada": "10.0.0.0/31"}'
```

En el navegador del equipo autorizado: `http://192.168.56.20/api/salud` y,
cuando esté el frontend, `http://192.168.56.20/`.

### 6.3 Logs

```bash
journalctl -u calculadora-ipv4 -e --no-pager          # gunicorn (accesos y errores)
journalctl -u calculadora-ipv4 -f                     # en vivo
sudo tail -n 50 /var/log/nginx/calculadora-ipv4.access.log
sudo tail -n 50 /var/log/nginx/calculadora-ipv4.error.log
journalctl -u nginx -e --no-pager
```

---

## 7. Diagnóstico de problemas

| Síntoma | Causa probable | Cómo confirmarlo | Solución |
|---|---|---|---|
| **502 Bad Gateway** en `/api/` y el log de Nginx dice `(13: Permission denied) while connecting to upstream` | SELinux bloquea Nginx → gunicorn | `sudo ausearch -m avc -ts recent -c nginx` muestra `denied { name_connect }` | `sudo setsebool -P httpd_can_network_connect 1` |
| **502** y el log dice `(111: Connection refused)` | gunicorn no está corriendo | `systemctl status calculadora-ipv4`, `journalctl -u calculadora-ipv4 -e` | Corregir el error del log y `sudo systemctl restart calculadora-ipv4` |
| **403 Forbidden** en archivos estáticos | Etiqueta SELinux incorrecta o permisos | `ls -Z /var/www/calculadora-ipv4`, `namei -l /var/www/calculadora-ipv4/index.html`, `sudo ausearch -m avc -ts recent` (`denied { read }`) | `sudo restorecon -Rv /var/www/calculadora-ipv4` y `sudo chmod -R u=rwX,go=rX /var/www/calculadora-ipv4` |
| **404** en `/` | Aún no se copió el frontend | `ls /var/www/calculadora-ipv4` | Paso 3.1 |
| Funciona en el servidor pero no desde otro equipo (tiempo agotado) | firewalld, IP equivocada o red de la VM | `sudo firewall-cmd --list-all`; `ping IP`; revisar que la VM esté en modo puente o red solo-anfitrión, no solo NAT | Paso 4; ajustar la red de la VM |
| Nginx no arranca | Error de configuración o puerto 80 ocupado | `sudo nginx -t`, `journalctl -u nginx -e`, `sudo ss -tlnp \| grep ':80 '` | Corregir la línea que indica `nginx -t`; parar el otro servicio (por ejemplo `httpd`) |
| El servicio falla con `status=203/EXEC` | Ruta de gunicorn equivocada o etiqueta SELinux de `/opt` | `ls -lZ /opt/calculadora-ipv4-api/venv/bin/gunicorn` | Repetir 1.4 y `sudo restorecon -Rv /opt/calculadora-ipv4-api` |
| El servicio falla con `ModuleNotFoundError` o `Permission denied` al leer `app.py` | Dependencias sin instalar o permisos | `journalctl -u calculadora-ipv4 -e` | Repetir 1.4 y 1.5 |

Si `ausearch` no muestra nada pero sospechas de SELinux, cambia a modo
permisivo **solo para probar** (`sudo setenforce 0`), repite la petición y
vuelve a `sudo setenforce 1`. Si con `0` funciona, el problema es SELinux.

---

## 8. Actualizar la aplicación

```bash
cd ~/calculadora-ipv4-backend          # con la versión nueva ya copiada
sudo cp -r app.py calc requirements.txt /opt/calculadora-ipv4-api/
sudo /opt/calculadora-ipv4-api/venv/bin/pip install -r /opt/calculadora-ipv4-api/requirements.txt
sudo chown -R root:calculadora /opt/calculadora-ipv4-api
sudo chmod -R u=rwX,g=rX,o= /opt/calculadora-ipv4-api
sudo restorecon -Rv /opt/calculadora-ipv4-api
sudo systemctl restart calculadora-ipv4
curl -s http://127.0.0.1/api/salud
```

---

## 9. Evidencias para el informe

Salidas que conviene capturar en el servidor (apartado 5 del informe):

```bash
cat /etc/rocky-release
python3 --version
systemctl status calculadora-ipv4 nginx --no-pager
sudo ss -tlnp | grep -E ':80 |:8000 '
sudo firewall-cmd --list-all
getenforce; getsebool httpd_can_network_connect
sudo nginx -t
```

Y desde el equipo autorizado: la salida de los curl del paso 6.2 (con su IP
visible, por ejemplo con `ip -4 addr` o `ipconfig` en la misma captura) y el
navegador abriendo `http://IP_DEL_SERVIDOR/`.
