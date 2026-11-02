"""Servidor de desarrollo: frontend y API en el mismo origen.

Reproduce en local lo que hace Nginx en producción: /api/ va a la API Flask
y el resto son los archivos estáticos del frontend. Así el frontend usa las
mismas rutas relativas (/api/calcular) y no hace falta CORS.

    python scripts/servidor_local.py                        # http://127.0.0.1:8080
    python scripts/servidor_local.py --puerto 9000
    python scripts/servidor_local.py --frontend /ruta/al/frontend/app

Solo para desarrollo. En producción no se usa: ver deploy/nginx/.
"""

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from flask import send_from_directory  # noqa: E402
from werkzeug.middleware.shared_data import SharedDataMiddleware  # noqa: E402

from app import create_app  # noqa: E402

# Por defecto, el repositorio del frontend clonado al lado de este.
FRONTEND_POR_DEFECTO = RAIZ.parent / "calculadora-ipv4-frontend" / "app"


def crear_app_local(frontend: Path):
    app = create_app()

    @app.get("/")
    def inicio():
        return send_from_directory(frontend, "index.html")

    # Los archivos que existan en el frontend se sirven tal cual; lo demás
    # (incluido /api/) sigue hacia Flask.
    app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {"/": str(frontend)})
    return app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--frontend", type=Path, default=FRONTEND_POR_DEFECTO,
                        help="carpeta app/ del frontend (por defecto: %(default)s)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--puerto", type=int, default=8080)
    args = parser.parse_args()

    frontend = args.frontend.resolve()
    if not (frontend / "index.html").is_file():
        print("No se encontró index.html en {}. Usa --frontend.".format(frontend), file=sys.stderr)
        return 1

    print("Frontend: {}".format(frontend))
    print("Abrir:    http://{}:{}/".format(args.host, args.puerto))
    crear_app_local(frontend).run(host=args.host, port=args.puerto, debug=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
