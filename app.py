"""API JSON de la calculadora IPv4 (Flask).

Ejecución local:   flask --app app run
Producción:        gunicorn --bind 127.0.0.1:8000 app:app   (detrás de Nginx)

Esta capa solo traduce HTTP <-> módulo ``calc``: lee la petición, decide
el formato de entrada (A o B), llama al cálculo y elige el código HTTP.
"""

import json
from typing import Any, Dict, Mapping

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException, MethodNotAllowed

from calc import mensajes
from calc.casos import CASOS_DE_PRUEBA
from calc.ipv4 import ErrorValidacion
from calc.respuesta import construir_error, respuesta_cidr, respuesta_direccion_mascara

# La petición más grande razonable ocupa menos de 100 bytes.
TAMANO_MAXIMO_CUERPO = 4 * 1024
CAMPOS_DE_ENTRADA = ("entrada", "direccion", "mascara")
MENSAJES_HTTP = {
    404: mensajes.ERROR_RUTA_NO_EXISTE,
    405: mensajes.ERROR_METODO_NO_PERMITIDO,
    413: mensajes.ERROR_PETICION_DEMASIADO_GRANDE,
}


class ErrorPeticion(Exception):
    """La petición no tiene la forma esperada (HTTP 400).

    Es distinto de ErrorValidacion (HTTP 422): aquí falla el JSON o la
    combinación de campos, no el contenido que escribió el usuario.
    """

    def __init__(self, campo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.campo = campo
        self.mensaje = mensaje


def _cuerpo_de_error(campo: str, mensaje: str) -> Dict[str, Any]:
    return {"ok": False, "errores": [{"campo": campo, "mensaje": mensaje}]}


def _leer_cuerpo_json() -> Dict[str, Any]:
    try:
        cuerpo = json.loads(request.get_data(as_text=True))
    except (ValueError, RecursionError):
        raise ErrorPeticion("cuerpo", mensajes.ERROR_JSON_MAL_FORMADO) from None
    if not isinstance(cuerpo, dict):
        raise ErrorPeticion("cuerpo", mensajes.ERROR_JSON_NO_OBJETO)
    return cuerpo


def _calcular(campos: Mapping[str, Any]) -> Dict[str, Any]:
    """Forma A si llega "entrada"; forma B si llega "direccion" o "mascara".

    En la forma B, un campo que no llega se trata como vacío, para que el
    usuario reciba el mensaje del campo que le falta.
    """
    forma_a = "entrada" in campos
    forma_b = "direccion" in campos or "mascara" in campos
    if forma_a and forma_b:
        raise ErrorPeticion("peticion", mensajes.ERROR_FORMATOS_MEZCLADOS)
    if not (forma_a or forma_b):
        raise ErrorPeticion("peticion", mensajes.ERROR_SIN_DATOS)
    for campo in CAMPOS_DE_ENTRADA:
        if campo in campos and not isinstance(campos[campo], str):
            raise ErrorPeticion("peticion", mensajes.error_campo_no_texto(campo))

    if forma_a:
        return respuesta_cidr(campos["entrada"])
    return respuesta_direccion_mascara(campos.get("direccion", ""), campos.get("mascara", ""))


def create_app() -> Flask:
    # Sin carpeta estática: Nginx sirve el frontend; Flask solo responde /api/.
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = TAMANO_MAXIMO_CUERPO
    app.json.sort_keys = False      # conserva el orden de las claves del contrato
    app.json.ensure_ascii = False   # "Dirección", no "Dirección"

    @app.post("/api/calcular")
    def calcular_post():
        return jsonify(_calcular(_leer_cuerpo_json()))

    @app.get("/api/calcular")
    def calcular_get():
        return jsonify(_calcular(request.args.to_dict()))

    @app.get("/api/casos-de-prueba")
    def casos_de_prueba():
        return jsonify([dict(caso) for caso in CASOS_DE_PRUEBA])

    @app.get("/api/salud")
    def salud():
        return jsonify({"ok": True})

    @app.errorhandler(ErrorValidacion)
    def error_de_validacion(error: ErrorValidacion):
        return jsonify(construir_error(error)), 422

    @app.errorhandler(ErrorPeticion)
    def error_de_peticion(error: ErrorPeticion):
        return jsonify(_cuerpo_de_error(error.campo, error.mensaje)), 400

    @app.errorhandler(HTTPException)
    def error_http(error: HTTPException):
        # 404, 405, 413 y los fallos inesperados (500) también responden JSON.
        codigo = error.code or 500
        if codigo >= 500:
            mensaje = mensajes.ERROR_INTERNO
        else:
            mensaje = MENSAJES_HTTP.get(codigo, mensajes.ERROR_PETICION_GENERICO)
        respuesta = jsonify(_cuerpo_de_error("peticion", mensaje))
        respuesta.status_code = codigo
        if isinstance(error, MethodNotAllowed) and error.valid_methods:
            respuesta.headers["Allow"] = ", ".join(error.valid_methods)
        return respuesta

    return app


app = create_app()
