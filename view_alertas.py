"""Alertas de inactividad calculadas a partir de los movimientos importados."""

import customtkinter as ctk

from theme import C, R, RIESGO, T, fuente, mono

UMBRAL_MEDIO = 90
UMBRAL_ALTO = 180

FILTROS = [
    ("Todas", 0),
    ("Más de 3 meses paradas", UMBRAL_MEDIO),
    ("Más de 6 meses (Riesgo Alto)", UMBRAL_ALTO),
]

def clasificar_riesgo(dias: int) -> tuple[str, str]:
    if dias >= UMBRAL_ALTO:
        return "Riesgo alto", RIESGO["alto"]
    if dias >= UMBRAL_MEDIO:
        return "Riesgo medio", RIESGO["medio"]
    return "Riesgo bajo", RIESGO["bajo"]


class AlertaCard(ctk.CTkFrame):
    def __init__(self, master, alerta, on_action):
        super().__init__(master, fg_color=C["card"], corner_radius=R.tarjeta,
                         border_width=1, border_color=C["border"])
        etiqueta, color = clasificar_riesgo(alerta["dias"])
        self.grid_columnconfigure(1, weight=1)

        # height=1 es necesario: un CTkFrame sin alto definido reserva 200 px
        # y estiraría la tarjeta. Con sticky="ns" la barra toma el alto real.
        ctk.CTkFrame(self, width=4, height=1, fg_color=color, corner_radius=2).grid(
            row=0, column=0, sticky="ns", padx=(12, 0), pady=12)

        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=1, sticky="ew", padx=16, pady=14)
        info.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(info, text=f"Exp. {alerta['expediente']}", font=mono(T.meta, "bold"),
                     text_color=C["cyan"], anchor="w").grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(info, text=alerta["caratula"], font=fuente(T.item, "bold"),
                     text_color=C["text"], anchor="w", justify="left"
                     ).grid(row=1, column=0, sticky="ew", pady=(2, 0))
        ctk.CTkLabel(info, text=alerta["juzgado"], font=mono(T.meta),
                     text_color=C["muted"], anchor="w"
                     ).grid(row=2, column=0, sticky="ew", pady=(2, 0))

        dias_box = ctk.CTkFrame(self, fg_color="transparent")
        dias_box.grid(row=0, column=2, sticky="e", padx=16)
        ctk.CTkLabel(dias_box, text=f"{alerta['dias']} días sin movimiento",
                     font=mono(T.cuerpo, "bold"), text_color=color, anchor="e"
                     ).grid(row=0, column=0, sticky="e")
        ctk.CTkLabel(dias_box, text=etiqueta.upper(), font=mono(T.etiqueta),
                     text_color=C["muted"], anchor="e").grid(row=1, column=0, sticky="e")

        ctk.CTkButton(self, text="Ver Proveído", height=36, width=140,
                      corner_radius=R.control,
                      fg_color=C["accent"], hover_color=C["accent_hover"],
                      font=fuente(T.cuerpo, "bold"),
                      command=lambda: on_action(alerta) if on_action else None
                      ).grid(row=0, column=3, padx=(0, 16), pady=14)


class AlertasView(ctk.CTkFrame):
    def __init__(self, master, alertas=None, on_action=None, **kwargs):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.alertas = list(alertas or [])
        self.on_action = on_action
        self.filtro_activo = 0
        self.filter_buttons = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._build_encabezado()
        self._build_filtros()
        self.lista = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.lista.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 20))
        self.lista.grid_columnconfigure(0, weight=1)
        self._render()

    def _build_encabezado(self):
        ctk.CTkLabel(self, text="Alertas de Inactividad",
                     font=fuente(T.titulo_pagina, "bold"), text_color=C["text"], anchor="w"
                     ).grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 4))

        self.subtitulo = ctk.CTkLabel(
            self,
            text="Antiguedad calculada a partir del ultimo movimiento importado. Este indicador no determina caducidad ni plazos procesales.",
            font=fuente(T.meta), text_color=C["muted"], anchor="w", justify="left")
        self.subtitulo.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        self.bind("<Configure>",
                  lambda e: self.subtitulo.configure(wraplength=max(e.width - 60, 300)), add="+")

    def _build_filtros(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 16))
        barra.grid_columnconfigure(len(FILTROS), weight=1)

        for i, (texto, _) in enumerate(FILTROS):
            btn = ctk.CTkButton(barra, text=texto, height=34, corner_radius=R.control,
                                font=fuente(T.meta),
                                command=lambda idx=i: self._set_filtro(idx))
            btn.grid(row=0, column=i, padx=(0 if i == 0 else 8, 0))
            self.filter_buttons.append(btn)

        self.contador = ctk.CTkLabel(barra, text="", font=mono(T.meta),
                                     text_color=C["muted"], anchor="e")
        self.contador.grid(row=0, column=len(FILTROS), sticky="e")
        self._estilo_filtros()

    def _set_filtro(self, idx):
        self.filtro_activo = idx
        self._estilo_filtros()
        self._render()

    def _estilo_filtros(self):
        for i, btn in enumerate(self.filter_buttons):
            activo = i == self.filtro_activo
            btn.configure(fg_color=C["accent"] if activo else C["card"],
                          hover_color=C["accent_hover"] if activo else C["card_hover"],
                          text_color=C["text"])

    def _visibles(self):
        minimo = FILTROS[self.filtro_activo][1]
        return sorted([a for a in self.alertas if a["dias"] >= minimo],
                      key=lambda a: a["dias"], reverse=True)

    def _render(self):
        for w in self.lista.winfo_children():
            w.destroy()

        visibles = self._visibles()
        total = len(visibles)
        self.contador.configure(text=f"{total} causa{'s' if total != 1 else ''}")

        if not visibles:
            mensaje = (
                "Sin alertas de inactividad registradas. Sincroniza con el SAE."
                if not self.alertas else "No hay alertas para este filtro."
            )
            ctk.CTkLabel(self.lista, text=mensaje,
                         font=fuente(T.cuerpo), text_color=C["muted"]
                         ).grid(row=0, column=0, pady=40)
            return

        for i, alerta in enumerate(visibles):
            AlertaCard(self.lista, alerta, on_action=self.on_action).grid(
                row=i, column=0, sticky="ew", pady=6)

    def actualizar_alertas(self, alertas):
        self.alertas = list(alertas or [])
        self._render()
