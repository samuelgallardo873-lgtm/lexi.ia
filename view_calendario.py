"""Calendario de actuaciones registradas e importadas desde el SAE."""

import calendar
from datetime import date
import sqlite3

import customtkinter as ctk

from theme import C, DIAS_SEMANA, MESES, PRIORIDAD, R, T, barra_acento, fuente, mono


class DayCell(ctk.CTkFrame):
    def __init__(self, master, dia, eventos, is_today, on_click):
        super().__init__(master, fg_color=C["card_row"], corner_radius=10, cursor="hand2")
        self.dia = dia
        self.is_today = is_today
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.num = ctk.CTkLabel(
            self, text=str(dia.day),
            font=mono(T.cuerpo, "bold" if is_today else "normal"),
            text_color=C["accent"] if is_today else C["text"])
        self.num.grid(row=0, column=0, pady=(8, 0))

        dots = ctk.CTkFrame(self, fg_color="transparent")
        dots.grid(row=1, column=0, pady=(2, 8))
        presentes = []
        for ev in eventos:
            if ev["prioridad"] not in presentes:
                presentes.append(ev["prioridad"])
        for i, p in enumerate(presentes):
            ctk.CTkFrame(dots, width=8, height=8, corner_radius=4,
                         fg_color=PRIORIDAD[p]["color"]).grid(row=0, column=i, padx=2)

        for w in (self, self.num, dots):
            w.bind("<Button-1>", lambda _e: on_click(self.dia))

    def set_selected(self, selected):
        self.configure(fg_color=C["accent"] if selected else C["card_row"])
        self.num.configure(
            text_color=C["text"] if selected else (C["accent"] if self.is_today else C["text"]))


class VencimientoCard(ctk.CTkFrame):
    def __init__(
        self, master, ev, on_delete=None, on_schedule_finding=None,
        on_discard_finding=None,
    ):
        super().__init__(master, fg_color=C["card_row"], corner_radius=12)
        self.es_actuacion = ev.get("es_actuacion", False)
        self.es_aviso = ev.get("es_aviso", False)
        self.es_sugerencia_ia = ev.get("es_sugerencia_ia", False)
        self.cumplido = False
        meta = PRIORIDAD[ev["prioridad"]]
        self.grid_columnconfigure(1, weight=1)

        # height=1: sin alto explícito el CTkFrame reservaría 200 px.
        ctk.CTkFrame(self, width=5, height=1, fg_color=meta["color"], corner_radius=3).grid(
            row=0, column=0, sticky="ns", padx=(10, 0), pady=12)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=0, column=1, sticky="ew", padx=14, pady=12)
        body.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            top, text="Fecha sugerida" if self.es_sugerencia_ia else ev["hora"],
            font=mono(T.meta if self.es_sugerencia_ia else T.item, "bold"),
                     text_color=C["text"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            top,
            text=" IA · revisar " if self.es_sugerencia_ia else f" {meta['label']} ",
            fg_color=meta["color"], corner_radius=8, height=22,
            text_color="#0A1322", font=mono(T.etiqueta, "bold"),
        ).grid(row=0, column=2, sticky="e")

        self.caratula = ctk.CTkLabel(
            body,
            text=(ev["caratula"] if self.es_aviso else
                  f"{ev['expediente']}  ·  {ev['caratula']}"),
            font=fuente(T.cuerpo, "bold"), text_color=C["text"],
            anchor="w", justify="left")
        self.caratula.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        self.diligencia = ctk.CTkLabel(body, text=ev.get("diligencia", ""),
                                       font=fuente(T.meta),
                                       text_color=C["muted"], anchor="w", justify="left")
        self.diligencia.grid(row=2, column=0, sticky="ew", pady=(2, 10))

        if self.es_sugerencia_ia:
            acciones = ctk.CTkFrame(body, fg_color="transparent")
            acciones.grid(row=3, column=0, sticky="ew")
            ctk.CTkButton(
                acciones, text="Revisar y agregar", height=32,
                corner_radius=8, fg_color=C["accent"],
                hover_color=C["accent_hover"], font=fuente(T.meta, "bold"),
                command=lambda: (
                    on_schedule_finding(ev) if on_schedule_finding else None
                ),
            ).pack(side="left")
            ctk.CTkButton(
                acciones, text="Descartar", width=88, height=32,
                corner_radius=8, fg_color=C["card"], hover_color=C["error"],
                font=fuente(T.meta),
                command=lambda: (
                    on_discard_finding(ev["id"]) if on_discard_finding else None
                ),
            ).pack(side="right")
        elif self.es_actuacion:
            ctk.CTkLabel(
                body, text="ACTUACIÓN REGISTRADA DESDE EL SAE",
                font=mono(T.etiqueta, "bold"), text_color=C["cyan"], anchor="w"
            ).grid(row=3, column=0, sticky="ew")
        elif self.es_aviso:
            acciones = ctk.CTkFrame(body, fg_color="transparent")
            acciones.grid(row=3, column=0, sticky="ew")
            ctk.CTkLabel(
                acciones, text="AVISO PERSONAL", font=mono(T.etiqueta, "bold"),
                text_color=C["warn"], anchor="w",
            ).pack(side="left")
            ctk.CTkButton(
                acciones, text="Eliminar", width=84, height=28, corner_radius=8,
                fg_color=C["card"], hover_color=C["error"],
                font=fuente(T.etiqueta),
                command=lambda: on_delete(ev["id"]) if on_delete else None,
            ).pack(side="right")
        else:
            self.btn = ctk.CTkButton(
                body, text="Marcar como cumplido", height=32, corner_radius=8,
                fg_color=C["accent"], hover_color=C["accent_hover"],
                font=fuente(T.meta, "bold"), command=self._toggle)
            self.btn.grid(row=3, column=0, sticky="ew")

        self.bind("<Configure>", self._on_resize)

    def _toggle(self):
        self.cumplido = not self.cumplido
        if self.cumplido:
            self.btn.configure(text="Cumplido · deshacer", fg_color=C["card_hover"],
                               hover_color=C["card"])
            self.caratula.configure(text_color=C["muted"])
        else:
            self.btn.configure(text="Marcar como cumplido", fg_color=C["accent"],
                               hover_color=C["accent_hover"])
            self.caratula.configure(text_color=C["text"])

    def _on_resize(self, event):
        wrap = max(event.width - 70, 160)
        self.caratula.configure(wraplength=wrap)
        self.diligencia.configure(wraplength=wrap)


class CalendarioView(ctk.CTkFrame):
    def __init__(
        self, master, vencimientos=None, on_export=None, hoy=None,
        on_add_aviso=None, on_delete_aviso=None, on_schedule_finding=None,
        on_discard_finding=None, **kwargs
    ):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.hoy = hoy or date.today()
        self.vencimientos = list(vencimientos or [])
        self.on_export = on_export
        self.on_add_aviso = on_add_aviso
        self.on_delete_aviso = on_delete_aviso
        self.on_schedule_finding = on_schedule_finding
        self.on_discard_finding = on_discard_finding
        self._modal_aviso = None
        self._error_agenda = None
        self.anio, self.mes = self.hoy.year, self.hoy.month
        self.seleccionado = self.hoy
        self.cells = {}

        self.grid_columnconfigure(0, weight=3, uniform="col")
        self.grid_columnconfigure(1, weight=2, uniform="col")
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_calendario()
        self._build_agenda()
        self._render_mes()

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 14))
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(bar, text="‹", width=38, height=36, corner_radius=10, fg_color=C["card"],
                      hover_color=C["card_hover"], text_color=C["text"],
                      font=fuente(T.titulo_app, "bold"),
                      command=self._mes_anterior).grid(row=0, column=0)

        self.titulo_mes = ctk.CTkLabel(bar, text="", font=fuente(T.saludo, "bold"),
                                       text_color=C["text"])
        self.titulo_mes.grid(row=0, column=1, padx=14)

        ctk.CTkButton(bar, text="›", width=38, height=36, corner_radius=10, fg_color=C["card"],
                      hover_color=C["card_hover"], text_color=C["text"],
                      font=fuente(T.titulo_app, "bold"),
                      command=self._mes_siguiente).grid(
                          row=0, column=2, padx=(0, 16))

        acciones = ctk.CTkFrame(bar, fg_color="transparent")
        acciones.grid(row=0, column=3, sticky="e")

        self.btn_export = ctk.CTkButton(
            acciones, text="Exportar calendario", height=36, corner_radius=10,
            fg_color=C["accent"], hover_color=C["accent_hover"],
            font=fuente(T.cuerpo, "bold"), command=self._exportar)
        self.btn_export.grid(row=0, column=2)

    def _build_calendario(self):
        cont = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=R.tarjeta,
                            border_width=1, border_color=C["border"])
        cont.grid(row=1, column=0, sticky="nsew", padx=(24, 12), pady=(0, 20))
        for i in range(7):
            cont.grid_columnconfigure(i, weight=1, uniform="dia")
        for r in range(1, 7):
            cont.grid_rowconfigure(r, weight=1, uniform="sem")

        for i, nombre in enumerate(DIAS_SEMANA):
            ctk.CTkLabel(cont, text=nombre.upper(), font=mono(T.etiqueta, "bold"),
                         text_color=C["muted"]).grid(row=0, column=i, pady=(14, 6))
        self.grid_cont = cont

        leyenda = ctk.CTkFrame(self, fg_color="transparent")
        leyenda.grid(row=2, column=0, sticky="w", padx=24, pady=(0, 18))
        for i, key in enumerate(("urgente", "habil", "info", "ia")):
            meta = PRIORIDAD[key]
            item = ctk.CTkFrame(leyenda, fg_color="transparent")
            item.grid(row=0, column=i, padx=(0 if i == 0 else 18, 0))
            ctk.CTkFrame(item, width=8, height=8, corner_radius=4,
                         fg_color=meta["color"]).grid(row=0, column=0, padx=(0, 6))
            ctk.CTkLabel(item, text=meta["label"], font=fuente(T.meta),
                         text_color=C["muted"]).grid(row=0, column=1)

    def _render_mes(self):
        for cell in self.cells.values():
            cell.destroy()
        self.cells.clear()

        self.titulo_mes.configure(text=f"{MESES[self.mes - 1]} {self.anio}")
        semanas = calendar.Calendar(firstweekday=0).monthdatescalendar(self.anio, self.mes)

        for r, semana in enumerate(semanas, start=1):
            for c, dia in enumerate(semana):
                if dia.month != self.mes:
                    continue
                cell = DayCell(self.grid_cont, dia, self._eventos_de(dia),
                               dia == self.hoy, self._on_day_click)
                cell.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
                self.cells[dia] = cell

        if self.seleccionado in self.cells:
            self.cells[self.seleccionado].set_selected(True)
        self._render_agenda()

    def _build_agenda(self):
        panel = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=R.tarjeta,
                             border_width=1, border_color=C["border"])
        panel.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=(12, 24), pady=(0, 20))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        encabezado = ctk.CTkFrame(panel, fg_color="transparent")
        encabezado.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 2))
        encabezado.grid_columnconfigure(0, weight=1)
        self.agenda_titulo = ctk.CTkLabel(
            encabezado, text="", font=fuente(T.seccion, "bold"),
            text_color=C["text"], anchor="w")
        self.agenda_titulo.grid(row=0, column=0, sticky="ew")
        self.error_agenda = ctk.CTkLabel(
            panel, text="", font=fuente(T.meta), text_color=C["error"],
            anchor="w", justify="left",
        )
        self.error_agenda.grid(
            row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        self.error_agenda.grid_remove()
        self.agenda_lista = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self.agenda_lista.grid(
            row=2, column=0, sticky="nsew", padx=(10, 0), pady=(0, 8))
        self.agenda_lista.grid_columnconfigure(0, weight=1)
        self.btn_agregar_aviso = ctk.CTkButton(
            panel, text="+ Agregar aviso", height=38, corner_radius=R.control,
            fg_color=C["accent"], hover_color=C["accent_hover"],
            font=fuente(T.cuerpo, "bold"), command=self._abrir_formulario_aviso,
        )
        self.btn_agregar_aviso.grid(
            row=3, column=0, sticky="e", padx=16, pady=(4, 14))

    def _render_agenda(self):
        for w in self.agenda_lista.winfo_children():
            w.destroy()

        d = self.seleccionado
        eventos = sorted(self._eventos_de(d), key=lambda e: e["hora"])
        self.agenda_titulo.configure(text=f"{d.day} de {MESES[d.month - 1]} de {d.year}")
        if not eventos:
            vacio = ctk.CTkFrame(
                self.agenda_lista, fg_color=C["card_row"], corner_radius=12)
            vacio.grid(row=0, column=0, sticky="ew", padx=4, pady=(18, 8))
            ctk.CTkLabel(
                vacio, text="—", font=fuente(25, "bold"),
                text_color=C["dim"],
            ).pack(pady=(18, 2))
            ctk.CTkLabel(
                vacio, text="Sin avisos ni actuaciones",
                font=fuente(T.item, "bold"), text_color=C["text"],
                anchor="center",
            ).pack(padx=16)
            ctk.CTkLabel(
                vacio,
                text="No hay eventos guardados para este día. Puedes agregar un aviso con el botón de abajo.",
                font=fuente(T.meta), text_color=C["muted"],
                justify="center", anchor="center", wraplength=290,
            ).pack(padx=18, pady=(6, 18))
            return

        for i, ev in enumerate(eventos):
            VencimientoCard(
                self.agenda_lista, ev,
                on_delete=self._eliminar_aviso,
                on_schedule_finding=self._abrir_revision_hallazgo,
                on_discard_finding=self._descartar_sugerencia,
            ).grid(row=i, column=0, sticky="ew", pady=5, padx=4)

    def _abrir_revision_hallazgo(self, hallazgo):
        if self._modal_aviso is not None:
            self._modal_aviso.lift()
            return
        if not self.on_schedule_finding:
            self.error_agenda.configure(
                text="No está configurada la confirmación de sugerencias IA.")
            self.error_agenda.grid()
            return

        raiz = self.winfo_toplevel()
        modal = ctk.CTkFrame(raiz, fg_color=C["page"], corner_radius=0)
        modal.place(relx=0, rely=0, relwidth=1, relheight=1)
        modal.lift()
        modal.grab_set()
        modal.bind("<Escape>", lambda event: self._cerrar_modal_aviso()
                   if event.widget is modal else None)
        self._modal_aviso = modal

        dialogo = ctk.CTkFrame(
            modal, width=560, height=620, fg_color=C["bg"],
            corner_radius=R.tarjeta, border_width=1, border_color=C["border"],
        )
        dialogo.grid_propagate(False)
        dialogo.place(relx=0.5, rely=0.5, anchor="center")
        dialogo.grid_columnconfigure(0, weight=1)
        encabezado = ctk.CTkFrame(dialogo, fg_color="transparent")
        encabezado.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 8))
        encabezado.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            encabezado, text="Revisar fecha sugerida por LEXI",
            font=fuente(T.seccion, "bold"), text_color=C["text"], anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            encabezado, text="×", width=30, height=30, corner_radius=8,
            fg_color="transparent", hover_color=C["card"],
            text_color=C["muted"], font=fuente(20),
            command=self._cerrar_modal_aviso,
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            dialogo,
            text="Comprueba la cita original. Nada se agregará hasta que confirmes.",
            font=fuente(T.meta), text_color=C["warn"], anchor="w",
            wraplength=510, justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 10))

        def campo(etiqueta, fila, valor="", placeholder=""):
            ctk.CTkLabel(
                dialogo, text=etiqueta, font=fuente(T.meta, "bold"),
                text_color=C["muted"], anchor="w",
            ).grid(row=fila, column=0, sticky="ew", padx=22)
            entrada = ctk.CTkEntry(
                dialogo, height=36, font=fuente(T.cuerpo),
                placeholder_text=placeholder,
            )
            entrada.insert(0, valor)
            entrada.grid(row=fila + 1, column=0, sticky="ew",
                         padx=22, pady=(3, 9))
            return entrada

        fecha = campo(
            "Fecha (AAAA-MM-DD)", 2, hallazgo["fecha"].isoformat())
        hora = campo("Hora (24 horas)", 4, "09:00")
        titulo = campo("Título", 6, hallazgo["caratula"])
        ctk.CTkLabel(
            dialogo, text="Detalle y cita que debes verificar",
            font=fuente(T.meta, "bold"), text_color=C["muted"], anchor="w",
        ).grid(row=8, column=0, sticky="ew", padx=22)
        detalle = ctk.CTkTextbox(
            dialogo, height=90, font=fuente(T.meta),
            fg_color=C["field"], text_color=C["text"],
        )
        detalle.insert("1.0", hallazgo["diligencia"])
        detalle.grid(row=9, column=0, sticky="ew", padx=22, pady=(3, 8))
        error = ctk.CTkLabel(
            dialogo, text="", font=fuente(T.etiqueta),
            text_color=C["error"], anchor="w", justify="left",
        )
        error.grid(row=10, column=0, sticky="ew", padx=22, pady=(0, 4))
        acciones = ctk.CTkFrame(dialogo, fg_color="transparent")
        acciones.grid(row=11, column=0, sticky="e", padx=22, pady=(4, 18))
        ctk.CTkButton(
            acciones, text="Cancelar", height=38, corner_radius=R.control,
            fg_color=C["card"], hover_color=C["card_hover"],
            font=fuente(T.cuerpo), command=self._cerrar_modal_aviso,
        ).pack(side="left", padx=(0, 8))

        def confirmar():
            try:
                evento = self.on_schedule_finding(
                    hallazgo["id"], fecha.get(), titulo.get(), hora.get(),
                    detalle.get("1.0", "end").strip(),
                )
            except (OSError, sqlite3.Error, ValueError, LookupError) as exc:
                error.configure(text=str(exc))
                return
            self.vencimientos = [
                evento_existente for evento_existente in self.vencimientos
                if not (
                    evento_existente.get("es_sugerencia_ia")
                    and evento_existente["id"] == hallazgo["id"]
                )
            ]
            self.vencimientos.append(evento)
            self.seleccionado = evento["fecha"]
            self._cerrar_modal_aviso()
            self._render_mes()

        ctk.CTkButton(
            acciones, text="Confirmar y agregar", height=38,
            corner_radius=R.control, fg_color=C["accent"],
            hover_color=C["accent_hover"], font=fuente(T.cuerpo, "bold"),
            command=confirmar,
        ).pack(side="left")

    def _descartar_sugerencia(self, hallazgo_id):
        if not self.on_discard_finding:
            return
        try:
            self.on_discard_finding(hallazgo_id)
        except (OSError, sqlite3.Error, LookupError, ValueError) as exc:
            self.error_agenda.configure(
                text=f"No se pudo descartar la sugerencia: {exc}")
            self.error_agenda.grid()
            return
        self.vencimientos = [
            evento for evento in self.vencimientos
            if not (
                evento.get("es_sugerencia_ia")
                and evento.get("id") == hallazgo_id
            )
        ]
        self.error_agenda.grid_remove()
        self._render_mes()

    def _abrir_formulario_aviso(self):
        if self._modal_aviso is not None:
            self._modal_aviso.lift()
            return

        raiz = self.winfo_toplevel()
        modal = ctk.CTkFrame(raiz, fg_color=C["page"], corner_radius=0)
        modal.place(relx=0, rely=0, relwidth=1, relheight=1)
        modal.lift()
        modal.grab_set()
        modal.bind("<Escape>", lambda event: self._cerrar_modal_aviso()
                   if event.widget is modal else None)
        self._modal_aviso = modal

        dialogo = ctk.CTkFrame(
            modal, width=520, height=480, fg_color=C["bg"],
            corner_radius=R.tarjeta, border_width=1, border_color=C["border"],
        )
        dialogo.grid_propagate(False)
        dialogo.place(relx=0.5, rely=0.5, anchor="center")
        dialogo.grid_columnconfigure(0, weight=1)

        encabezado = ctk.CTkFrame(dialogo, fg_color="transparent")
        encabezado.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 10))
        encabezado.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            encabezado, text="Agregar aviso al calendario",
            font=fuente(T.seccion, "bold"), text_color=C["text"], anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            encabezado, text="×", width=30, height=30, corner_radius=8,
            fg_color="transparent", hover_color=C["card"], text_color=C["muted"],
            font=fuente(20), command=self._cerrar_modal_aviso,
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            dialogo, text=f"Fecha seleccionada: {self.seleccionado.strftime('%d/%m/%Y')}",
            font=fuente(T.meta), text_color=C["cyan"], anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 14))

        ctk.CTkLabel(
            dialogo, text="Título", font=fuente(T.meta, "bold"),
            text_color=C["muted"], anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=22)
        titulo = ctk.CTkEntry(
            dialogo, height=38, placeholder_text="Ej.: Presentar documentación",
            font=fuente(T.cuerpo),
        )
        titulo.grid(row=3, column=0, sticky="ew", padx=22, pady=(4, 12))

        ctk.CTkLabel(
            dialogo, text="Hora (24 horas)", font=fuente(T.meta, "bold"),
            text_color=C["muted"], anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=22)
        hora = ctk.CTkEntry(dialogo, height=36, font=fuente(T.cuerpo))
        hora.insert(0, "09:00")
        hora.grid(row=5, column=0, sticky="ew", padx=22, pady=(4, 12))

        ctk.CTkLabel(
            dialogo, text="Detalle (opcional)", font=fuente(T.meta, "bold"),
            text_color=C["muted"], anchor="w",
        ).grid(row=6, column=0, sticky="ew", padx=22)
        detalle = ctk.CTkEntry(
            dialogo, height=36, placeholder_text="Información adicional",
            font=fuente(T.cuerpo),
        )
        detalle.grid(row=7, column=0, sticky="ew", padx=22, pady=(4, 8))
        error = ctk.CTkLabel(
            dialogo, text="", height=28, font=fuente(T.etiqueta),
            text_color=C["error"],
            anchor="w", justify="left",
        )
        error.grid(row=8, column=0, sticky="ew", padx=22, pady=(0, 4))

        acciones = ctk.CTkFrame(dialogo, fg_color="transparent")
        acciones.grid(row=9, column=0, sticky="e", padx=22, pady=(4, 18))
        ctk.CTkButton(
            acciones, text="Cancelar", height=38, corner_radius=R.control,
            fg_color=C["card"], hover_color=C["card_hover"],
            font=fuente(T.cuerpo), command=self._cerrar_modal_aviso,
        ).pack(side="left", padx=(0, 8))

        def guardar():
            if not self.on_add_aviso:
                error.configure(
                    text="No está configurado el guardado de avisos.",
                )
                return
            try:
                evento = self.on_add_aviso(
                    self.seleccionado, titulo.get(), hora.get(), detalle.get())
            except (OSError, sqlite3.Error, ValueError) as exc:
                error.configure(text=str(exc))
                return
            self.vencimientos.append(evento)
            self._render_mes()
            self._cerrar_modal_aviso()

        ctk.CTkButton(
            acciones, text="Guardar aviso", height=38, corner_radius=R.control,
            fg_color=C["accent"], hover_color=C["accent_hover"],
            font=fuente(T.cuerpo, "bold"), command=guardar,
        ).pack(side="left")
        titulo.focus_set()

    def _cerrar_modal_aviso(self):
        if self._modal_aviso is None:
            return
        modal = self._modal_aviso
        self._modal_aviso = None
        modal.grab_release()
        modal.destroy()

    def _eliminar_aviso(self, aviso_id):
        if not self.on_delete_aviso:
            return
        try:
            self.on_delete_aviso(aviso_id)
        except (OSError, sqlite3.Error, LookupError, ValueError) as exc:
            self.error_agenda.configure(text=f"No se pudo eliminar el aviso: {exc}")
            self.error_agenda.grid()
            return
        self.error_agenda.grid_remove()
        self.vencimientos = [
            evento for evento in self.vencimientos
            if evento.get("id") != aviso_id
        ]
        self._render_mes()

    def _eventos_de(self, dia):
        return [e for e in self.vencimientos if e["fecha"] == dia]

    def _on_day_click(self, dia):
        if self.seleccionado in self.cells:
            self.cells[self.seleccionado].set_selected(False)
        self.seleccionado = dia
        self.cells[dia].set_selected(True)
        self._render_agenda()

    def _mes_anterior(self):
        self.mes -= 1
        if self.mes == 0:
            self.mes, self.anio = 12, self.anio - 1
        self._render_mes()

    def _mes_siguiente(self):
        self.mes += 1
        if self.mes == 13:
            self.mes, self.anio = 1, self.anio + 1
        self._render_mes()

    def _ir_a_hoy(self):
        self.anio, self.mes = self.hoy.year, self.hoy.month
        self.seleccionado = self.hoy
        self._render_mes()

    def actualizar_eventos(self, eventos):
        self.vencimientos = list(eventos)
        self._render_mes()

    def _exportar(self):
        if self.on_export:
            self.on_export(self.vencimientos)
        else:
            self.btn_export.configure(text="Exportación aún no implementada")
            self.after(2000,
                       lambda: self.btn_export.configure(text="Exportar calendario"))
