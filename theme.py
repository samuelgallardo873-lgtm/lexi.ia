"""
LexBot - Sistema visual compartido: paleta, tipografía, espaciados y radios.

Todas las vistas importan desde aquí, así un cambio de color o de fuente se
hace en un solo lugar.

Uso de tipografía:
    from theme import fuente, mono
    ctk.CTkLabel(master, text="Hola", font=fuente(14, "bold"))
    ctk.CTkLabel(master, text="12.345/2022", font=mono(12))

Las fuentes se resuelven en la primera llamada, no al importar, porque
CTkFont necesita que la ventana principal ya exista.

El tamaño general de la interfaz lo controla el usuario desde Configuración.
Se aplica con el escalado propio de CustomTkinter (ver aplicar_escala), que
agranda tipografía y controles a la vez: así nada queda apretado.
"""

import tkinter.font as tkfont

import customtkinter as ctk

import ajustes

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------
COLORS = {
    # Fondos
    "page": "#060C18",        # fondo exterior de la ventana
    "bg": "#0A1322",          # área de contenido
    "sidebar": "#080F1C",     # barra lateral
    "topbar": "#0B1426",      # barra superior
    "card": "#111D31",        # tarjetas
    "card_row": "#17233A",    # filas dentro de una tarjeta
    "card_hover": "#1D2B45",  # hover de filas y botones neutros
    "card_sel": "#1E3360",    # fila seleccionada
    "field": "#17233A",       # campos de formulario
    "border": "#223350",      # bordes de tarjeta
    "border_soft": "#1A2840",

    # Acentos
    "accent": "#2F6FED",      # azul principal (botones, selección)
    "accent_hover": "#2457C4",
    "accent_soft": "#1B3A72",  # fondo de chips azules
    "cyan": "#2DD4E8",        # datos y números de expediente
    "gold": "#C8A24A",        # marca: balanza, filetes, detalles
    "gold_soft": "#3A2F17",
    "violet": "#8B7CF6",

    # Texto
    "text": "#EAF0FA",
    "text_soft": "#C6D3E6",
    "muted": "#8698B4",
    "dim": "#64799A",

    # Estados
    "ok": "#2FBF6B",
    "warn": "#E8A33D",
    "error": "#EF5350",
    "pink": "#F472B6",
}

C = COLORS

# Barras superiores de las tarjetas. CustomTkinter no dibuja degradados, así
# que cada entrada guarda el par del mockup y el color plano que se usa.
ACENTOS_TARJETA = {
    "alertas": {"gradiente": ("#E8A33D", "#F472B6"), "plano": "#E8835A"},
    "agenda": {"gradiente": ("#2DD4E8", "#2F6FED"), "plano": "#2DD4E8"},
    "caducidad": {"gradiente": ("#E8A33D", "#EF5350"), "plano": "#E8A33D"},
    "movimientos": {"gradiente": ("#2F6FED", "#8B7CF6"), "plano": "#2F6FED"},
    "marca": {"gradiente": ("#C8A24A", "#8A6A22"), "plano": "#C8A24A"},
}

PRIORIDAD = {
    "urgente": {"label": "Urgente", "color": COLORS["error"]},
    "habil": {"label": "Plazo hábil", "color": COLORS["warn"]},
    "info": {"label": "Información", "color": "#5F7698"},
    "ia": {"label": "Sugerencia IA", "color": COLORS["violet"]},
}

RIESGO = {
    "alto": COLORS["error"],
    "medio": COLORS["warn"],
    "bajo": "#5F7698",
}

ESTADO_CAUSA = {
    "Activo": COLORS["ok"],
    "En trámite": COLORS["accent"],
    "Paralizado": COLORS["warn"],
    "Archivado": COLORS["dim"],
}

# ---------------------------------------------------------------------------
# Tipografía
# ---------------------------------------------------------------------------
FAMILIAS_SANS = ["Inter", "Segoe UI Variable Text", "Segoe UI", "Helvetica Neue",
                 "DejaVu Sans", "Arial"]
FAMILIAS_MONO = ["JetBrains Mono", "Cascadia Mono", "Consolas", "SF Mono",
                 "DejaVu Sans Mono", "Courier New"]

_resueltas = {}


def _familia(preferidas, clave):
    """Devuelve la primera familia instalada; cachea el resultado."""
    if clave in _resueltas:
        return _resueltas[clave]
    try:
        disponibles = {f.lower() for f in tkfont.families()}
    except RuntimeError:          # todavía no hay ventana creada
        disponibles = set()
    elegida = next((f for f in preferidas if f.lower() in disponibles), preferidas[-1])
    _resueltas[clave] = elegida
    return elegida


def fuente(size=14, weight="normal", slant="roman", underline=False):
    """Tipografía de interfaz."""
    return ctk.CTkFont(family=_familia(FAMILIAS_SANS, "sans"), size=size,
                       weight=weight, slant=slant, underline=underline)


def mono(size=13, weight="normal"):
    """Monoespaciada: números de expediente, fechas, datos técnicos."""
    return ctk.CTkFont(family=_familia(FAMILIAS_MONO, "mono"), size=size, weight=weight)


def aplicar_escala(nombre=None):
    """
    Aplica el tamaño general elegido por el usuario.

    Usa el escalado de CustomTkinter, que reajusta en vivo los widgets ya
    creados: no hace falta reiniciar la app ni reconstruir las vistas.
    """
    if nombre:
        ajustes.guardar(escala=nombre)
    factor = ajustes.factor_escala()
    ctk.set_widget_scaling(factor)
    return factor


# Escala tipográfica. Son los tamaños base: el factor del usuario se aplica
# encima. Nada baja de 11 px, el mínimo cómodo en pantallas Windows comunes.
class T:
    titulo_app = 19      # "LexBot SAE" en la barra lateral
    titulo_pagina = 27   # título de cada vista
    saludo = 25          # encabezado del dashboard y del detalle
    kpi = 30             # número grande de las métricas
    seccion = 16         # título de tarjeta
    item = 15            # título de un ítem de lista
    cuerpo = 14          # texto normal
    meta = 13            # metadatos y datos monoespaciados
    etiqueta = 11        # rótulos en mayúsculas e insignias


# ---------------------------------------------------------------------------
# Espaciado y radios
# ---------------------------------------------------------------------------
class S:
    xs = 4
    sm = 8
    md = 12
    lg = 16
    xl = 20       # margen de página
    tarjeta = 18  # relleno interno de una tarjeta


class R:
    chip = 8
    control = 10
    tarjeta = 14


def barra_acento(master, clave, alto=3):
    """
    Barra de acento superior de una tarjeta.

    En el diseño es un degradado; CustomTkinter no los dibuja, así que se usa
    el color plano equivalente definido en ACENTOS_TARJETA.
    """
    color = ACENTOS_TARJETA.get(clave, {}).get("plano", COLORS["accent"])
    return ctk.CTkFrame(master, height=alto, width=1, fg_color=color, corner_radius=2)


# ---------------------------------------------------------------------------
# Calendario
# ---------------------------------------------------------------------------
MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
