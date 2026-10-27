"""Dashboard con métricas y novedades locales importadas desde el SAE."""

from datetime import datetime

import customtkinter as ctk

from theme import C, PRIORIDAD, R, T, barra_acento, fuente, mono


def _una_novedad_por_expediente(items):
    vistos = set()
    ultimas = []
    for item in items:
        expediente = item["expediente"]
        if expediente not in vistos:
            vistos.add(expediente)
            ultimas.append(item)
    return ultimas


class KpiCard(ctk.CTkFrame):
    def __init__(self, master, title, value, value_color):
        super().__init__(master, fg_color=C["card"], corner_radius=R.tarjeta,
                         border_width=1, border_color=C["border"])
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title.upper(), text_color=C["muted"],
                     font=mono(T.etiqueta), anchor="w"
                     ).grid(row=0, column=0, padx=18, pady=(16, 2), sticky="ew")
        ctk.CTkLabel(self, text=value, text_color=value_color,
                     font=fuente(T.kpi, "bold"), anchor="w"
                     ).grid(row=1, column=0, padx=18, pady=(0, 16), sticky="ew")


class NovedadRow(ctk.CTkFrame):
    def __init__(self, master, item, on_click):
        super().__init__(master, fg_color=C["card_row"], corner_radius=12, cursor="hand2")
        self.grid_columnconfigure(0, weight=1)
        meta = PRIORIDAD[item["prioridad"]]

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 2))
        top.grid_columnconfigure(1, weight=1)

        # El número de expediente va en monoespaciada: alinea verticalmente
        # entre filas y se distingue del texto de la carátula.
        self.exp = ctk.CTkLabel(top, text=f"Exp. {item['expediente']}", anchor="w",
                                font=mono(T.meta, "bold"), text_color=C["cyan"])
        self.exp.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.badge = ctk.CTkLabel(
            top, text=f" {meta['label'].upper()} ", fg_color=meta["color"],
            corner_radius=R.chip, height=22, text_color="#0A1322",
            font=mono(T.etiqueta, "bold"))
        self.badge.grid(row=0, column=2, sticky="e", padx=(8, 0))

        self.title = ctk.CTkLabel(
            self, text=item.get("titulo") or item["caratula"], anchor="w",
                                  font=fuente(T.item, "bold"), text_color=C["text"])
        self.title.grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 0))

        self.meta = ctk.CTkLabel(
            self, text=f"{item['caratula']}  ·  {item['fecha']}", anchor="w",
            text_color=C["muted"], font=mono(T.meta))
        self.meta.grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 12))

        for w in (self, top, self.exp, self.title, self.badge, self.meta):
            w.bind("<Button-1>", lambda _e: on_click())

    def set_selected(self, selected):
        self.configure(fg_color=C["card_sel"] if selected else C["card_row"])


class NovedadesPanel(ctk.CTkFrame):
    def __init__(self, master, items, on_select):
        super().__init__(master, fg_color=C["card"], corner_radius=R.tarjeta,
                         border_width=1, border_color=C["border"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.rows = []

        barra_acento(self, "alertas").grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.grid(row=1, column=0, sticky="ew", padx=18, pady=(12, 8))
        cab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cab, text="NOVEDADES RECIENTES", font=fuente(T.seccion, "bold"),
                     text_color=C["text"], anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(cab, text="Proveídos y cédulas leídos en el último barrido",
                     font=fuente(T.meta), text_color=C["muted"], anchor="w"
                     ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.contador = ctk.CTkLabel(
            cab, text=f" {len(items)} ", fg_color=C["accent_soft"],
            corner_radius=R.chip, height=24, text_color=C["cyan"],
            font=mono(T.etiqueta, "bold"))
        self.contador.grid(row=0, column=1, rowspan=2, sticky="e")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        scroll.grid_columnconfigure(0, weight=1)

        self.scroll = scroll
        self.on_select = on_select
        self.refresh(items)

    def refresh(self, items):
        for child in self.scroll.winfo_children():
            child.destroy()
        self.rows = []
        self.contador.configure(text=f" {len(items)} ")
        if not items:
            ctk.CTkLabel(
                self.scroll, text="Todavía no hay actuaciones guardadas desde el SAE.",
                font=fuente(T.cuerpo), text_color=C["muted"]
            ).grid(row=0, column=0, pady=28)
            return
        for i, item in enumerate(items):
            row = NovedadRow(self.scroll, item, on_click=lambda idx=i: self.on_select(idx))
            row.grid(row=i, column=0, sticky="ew", padx=4, pady=4)
            self.rows.append(row)

    def set_selected(self, index):
        for i, row in enumerate(self.rows):
            row.set_selected(i == index)


class PreviewPanel(ctk.CTkFrame):
    def __init__(self, master, on_open_expediente=None):
        super().__init__(master, fg_color=C["card"], corner_radius=R.tarjeta,
                         border_width=1, border_color=C["border"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        self.on_open_expediente = on_open_expediente
        self.item_actual = None

        barra_acento(self, "agenda").grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))

        ctk.CTkLabel(self, text="VISTA PREVIA DE ACTUACIÓN", font=fuente(T.seccion, "bold"),
                     text_color=C["text"], anchor="w"
                     ).grid(row=1, column=0, sticky="ew", padx=18, pady=(12, 8))

        self.exp = ctk.CTkLabel(self, text="", font=mono(T.meta, "bold"),
                                text_color=C["cyan"], anchor="w")
        self.exp.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 2))

        self.title = ctk.CTkLabel(self, text="", font=fuente(T.item, "bold"),
                                  text_color=C["text"], anchor="w", justify="left")
        self.title.grid(row=3, column=0, sticky="ew", padx=18)

        self.meta = ctk.CTkLabel(self, text="", font=mono(T.meta),
                                 text_color=C["muted"], anchor="w", justify="left")
        self.meta.grid(row=4, column=0, sticky="ew", padx=18, pady=(4, 14))

        box = ctk.CTkFrame(self, fg_color=C["card_row"], corner_radius=12)
        box.grid(row=5, column=0, sticky="nsew", padx=18)
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(box, text="TEXTO ORIGINAL DEL SAE", font=mono(T.etiqueta, "bold"),
                     text_color=C["muted"], anchor="w"
                     ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))

        self.summary_scroll = ctk.CTkScrollableFrame(
            box, fg_color="transparent", height=190,
            scrollbar_button_color=C["card_hover"],
            scrollbar_button_hover_color=C["accent"],
        )
        self.summary_scroll.grid(
            row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))
        self.summary_scroll.grid_columnconfigure(0, weight=1)
        self.summary = ctk.CTkLabel(
            self.summary_scroll, text="", font=fuente(T.cuerpo),
            text_color=C["text_soft"], anchor="w", justify="left",
        )
        self.summary.grid(row=0, column=0, sticky="ew", padx=8, pady=(0, 8))

        limit_box = ctk.CTkFrame(self, fg_color="transparent")
        limit_box.grid(row=6, column=0, sticky="ew", padx=18, pady=(14, 0))
        limit_box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(limit_box, text="REFERENCIA DE PLAZO", font=mono(T.etiqueta, "bold"),
                     text_color=C["muted"], anchor="w").grid(row=0, column=0, sticky="ew")

        self.limit = ctk.CTkLabel(limit_box, text="", font=mono(17, "bold"),
                                  text_color=C["cyan"], anchor="w")
        self.limit.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        acciones = ctk.CTkFrame(self, fg_color="transparent")
        acciones.grid(row=7, column=0, sticky="ew", padx=18, pady=18)
        for column in range(2):
            acciones.grid_columnconfigure(column, weight=1, uniform="preview_action")
        self.btn_calendar = ctk.CTkButton(
            acciones, text="Agregar al calendario", height=40,
            corner_radius=R.control, font=fuente(T.meta, "bold"),
            fg_color=C["accent"], hover_color=C["accent_hover"], command=self._on_add)
        self.btn_calendar.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_expediente = ctk.CTkButton(
            acciones, text="Ver expediente", height=40,
            corner_radius=R.control, font=fuente(T.meta, "bold"),
            fg_color=C["card_hover"], hover_color=C["border"],
            text_color=C["text_soft"], command=self._on_open_expediente,
        )
        self.btn_expediente.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Se enlaza al final: _on_resize usa etiquetas creadas más arriba.
        self.bind("<Configure>", self._on_resize)

    def _on_add(self):
        self.btn_calendar.configure(text="Agregado al calendario", state="disabled")

    def _on_open_expediente(self):
        if self.item_actual and self.on_open_expediente:
            self.on_open_expediente(self.item_actual)

    def _on_resize(self, event):
        wrap = max(event.width - 60, 200)
        for label in (self.title, self.meta, self.summary):
            label.configure(wraplength=wrap)

    def show(self, item):
        self.item_actual = item
        self.exp.configure(text=f"Exp. {item['expediente']}")
        self.title.configure(text=item.get("titulo") or item["caratula"])
        self.meta.configure(text=f"{item['fuero']}  ·  Novedad del {item['fecha']}")
        self.summary.configure(text=item["resumen"])
        self.limit.configure(text=item["limite"])
        self.btn_calendar.configure(text="Agregar al calendario", state="normal")
        self.btn_expediente.configure(state="normal")

    def show_empty(self):
        self.item_actual = None
        self.exp.configure(text="Sin actuaciones")
        self.title.configure(text="Sin novedades registradas.")
        self.meta.configure(text="Los movimientos aparecerán después de sincronizar con el SAE.")
        self.summary.configure(
            text="No hay actuaciones importadas para los expedientes monitoreados.")
        self.limit.configure(text="No se calculan plazos automáticamente.")
        self.btn_calendar.configure(text="Sin evento para agregar", state="disabled")
        self.btn_expediente.configure(state="disabled")


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, novedades=None, on_sync=None,
                 expedientes_monitoreados=0, on_open_expediente=None,
                 on_summarize=None, **kwargs):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.novedades_data = _una_novedad_por_expediente(novedades or [])
        self.on_sync = on_sync
        self.on_open_expediente = on_open_expediente
        self.on_summarize = on_summarize
        self.expedientes_monitoreados = expedientes_monitoreados

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_kpis()
        self._build_body()

        if self.novedades_data:
            self.novedades.set_selected(0)
            self.preview.show(self.novedades_data[0])
        else:
            self.preview.show_empty()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 16))
        header.grid_columnconfigure(0, weight=1)

        titulo = ctk.CTkFrame(header, fg_color="transparent")
        titulo.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(titulo, text="Panel de Control", font=fuente(T.saludo, "bold"),
                     text_color=C["text"], anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(titulo, text="Monitoreo de expedientes y plazos procesales",
                     font=fuente(T.meta), text_color=C["muted"], anchor="w"
                     ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e")

        self.sync_label = ctk.CTkLabel(actions, text="Último barrido: sin datos",
                                       text_color=C["muted"], font=mono(T.meta))
        self.sync_label.grid(row=0, column=0, padx=(0, 16))

        for columna, (dias, etiqueta) in (
            (1, (1, "24 h")), (2, (30, "30 d")),
        ):
            ctk.CTkButton(
                actions, text=f"Resumen IA · {etiqueta}", height=38,
                corner_radius=R.control, fg_color=C["card"],
                hover_color=C["card_hover"], text_color=C["cyan"],
                font=fuente(T.meta, "bold"),
                command=lambda periodo=dias: self._on_summarize(periodo),
            ).grid(row=0, column=columna, padx=(0, 8))

        self.btn_track = ctk.CTkButton(
            actions, text="Sincronizar Ahora", height=38, corner_radius=R.control,
            fg_color=C["accent"], hover_color=C["accent_hover"],
            font=fuente(T.cuerpo, "bold"), command=self._on_track)
        self.btn_track.grid(row=0, column=3)

    def _on_summarize(self, periodo_dias):
        if self.on_summarize:
            self.on_summarize(periodo_dias)
        else:
            self.sync_label.configure(text="No está configurado el resumen IA local.")

    def _build_kpis(self):
        kpis = ctk.CTkFrame(self, fg_color="transparent")
        kpis.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        for i in range(4):
            kpis.grid_columnconfigure(i, weight=1, uniform="kpi")

        data = [
            ("Expedientes monitoreados", str(self.expedientes_monitoreados), C["text"]),
            ("Vencimientos calculados", "—", C["warn"]),
            ("Actuaciones recientes", str(len(self.novedades_data)), C["cyan"]),
            ("Alertas de inactividad", "—", C["error"]),
        ]
        self.kpi_values = {}
        for col, (title, value, color) in enumerate(data):
            card = KpiCard(kpis, title, value, color)
            card.grid(
                row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 12, 0))
            self.kpi_values[title] = card.winfo_children()[-1]

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 20))
        body.grid_columnconfigure(0, weight=3, uniform="body")
        body.grid_columnconfigure(1, weight=2, uniform="body")
        body.grid_rowconfigure(0, weight=1)

        self.novedades = NovedadesPanel(body, self.novedades_data, on_select=self._on_select)
        self.novedades.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self.preview = PreviewPanel(
            body, on_open_expediente=self.on_open_expediente)
        self.preview.grid(row=0, column=1, sticky="nsew")

    def _on_select(self, index):
        self.novedades.set_selected(index)
        self.preview.show(self.novedades_data[index])

    def _on_track(self):
        if not self.on_sync:
            self.sync_label.configure(text="No hay una acción de sincronización configurada.")
            return
        self.btn_track.configure(state="disabled", text="Sincronizando...")
        self.sync_label.configure(text="Barrido en curso...")
        self.on_sync(self._finish_track)

    def _finish_track(self, resultado=None, error=None):
        self.btn_track.configure(state="normal", text="Sincronizar Ahora")
        if error:
            self.sync_label.configure(text=f"Falló el barrido: {error}")
            return
        hora = datetime.now().strftime("%H:%M")
        nuevas = getattr(resultado, "actuaciones_nuevas", 0)
        self.sync_label.configure(
            text=f"Último barrido: {hora} · {nuevas} actuaciones nuevas")

    def actualizar_datos(self, novedades, expedientes_monitoreados):
        self.novedades_data = _una_novedad_por_expediente(novedades)
        self.expedientes_monitoreados = expedientes_monitoreados
        self.kpi_values["Expedientes monitoreados"].configure(
            text=str(expedientes_monitoreados))
        self.kpi_values["Actuaciones recientes"].configure(text=str(len(novedades)))
        self.novedades.refresh(self.novedades_data)
        if self.novedades_data:
            self.novedades.set_selected(0)
            self.preview.show(self.novedades_data[0])
        else:
            self.preview.show_empty()
