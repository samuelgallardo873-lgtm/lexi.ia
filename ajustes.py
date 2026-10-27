"""
LexBot - Ajustes del usuario guardados en disco.

Se guardan en la carpeta personal del equipo, no en la del programa, para que
sobrevivan a una actualización de la app:

    Windows:  C:\\Users\\<usuario>\\.lexbot\\ajustes.json

Acá van solo preferencias de interfaz y datos del profesional. Las
credenciales del SAE NO se guardan en este archivo: van cifradas en el
almacén de credenciales del sistema operativo.
"""

import json
from pathlib import Path

CARPETA = Path.home() / ".lexbot"
ARCHIVO = CARPETA / "ajustes.json"

# Opciones de tamaño de fuente. El valor es el factor de escala que se aplica
# a toda la interfaz: tipografía y también alto de botones y campos, para que
# nada quede apretado al agrandar.
ESCALAS = {
    "Compacto": 0.90,
    "Normal": 1.00,
    "Cómodo": 1.12,
    "Grande": 1.25,
}
ESCALA_POR_DEFECTO = "Normal"

POR_DEFECTO = {
    "escala": ESCALA_POR_DEFECTO,
    "nombre": "Dr. Matrícula Federal",
    "matricula": "T° XIV F° 208 · C.P.A.T.",
    "foto": "",          # ruta a una imagen; vacío = se muestran las iniciales
}

_cache = None


def cargar():
    """Lee los ajustes del disco. Ante cualquier problema, usa los valores por defecto."""
    global _cache
    if _cache is not None:
        return _cache

    datos = dict(POR_DEFECTO)
    try:
        if ARCHIVO.exists():
            guardado = json.loads(ARCHIVO.read_text(encoding="utf-8"))
            if isinstance(guardado, dict):
                datos.update({k: v for k, v in guardado.items() if k in POR_DEFECTO})
    except (OSError, ValueError):
        # Archivo ilegible o corrupto: se sigue con los valores por defecto.
        pass

    if datos.get("escala") not in ESCALAS:
        datos["escala"] = ESCALA_POR_DEFECTO
    _cache = datos
    return _cache


def guardar(**cambios):
    """Guarda los cambios indicados. Devuelve True si se pudo escribir el archivo."""
    datos = cargar()
    datos.update({k: v for k, v in cambios.items() if k in POR_DEFECTO})
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        ARCHIVO.write_text(json.dumps(datos, indent=2, ensure_ascii=False),
                           encoding="utf-8")
        return True
    except OSError:
        return False


def factor_escala():
    return ESCALAS.get(cargar().get("escala"), 1.0)


def iniciales(nombre=None):
    """Iniciales para el avatar cuando no hay foto cargada."""
    nombre = nombre if nombre is not None else cargar().get("nombre", "")
    # Se descartan los tratamientos para no terminar con "DR".
    palabras = [p for p in nombre.replace(".", " ").split()
                if p.lower() not in ("dr", "dra", "doctor", "doctora")]
    letras = [p[0].upper() for p in palabras[:2] if p]
    return "".join(letras) or "LB"
