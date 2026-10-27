"""Interfaz de conversaciones locales de LEXI."""

import re
import sqlite3

import customtkinter as ctk

from theme import C, R, T, fuente, mono

CONSULTAS_SUGERIDAS = (
    "¿Cuál fue la última actuación de mi expediente?",
    "¿Qué información aparece en las actuaciones más recientes?",
    "¿Qué dice la última actuación que guardé?",
    "Dame las últimas novedades de todos mis expedientes.",
)


def _contenido_visible(contenido):
    contenido = re.sub(
        r"(?is)\n+\s*(?:Fuentes(?: consultadas)?\s*:|Referencias\s*:|"
        r"No se pudo validar una cita concreta).*?$",
        "",
        str(contenido or ""),
    )
    contenido = re.sub(
        r"(?is)\n+\s*Las fechas identificadas son sugerencias.*?$",
        "",
        contenido,
    )
    contenido = re.sub(
        r"(?im)^\s*Cita:\s*.*\[\s*N\d+\s*\]\s*$",
        "",
        contenido,
    )
    contenido = re.sub(
        r"(?im)^\s*\[?\s*N\d+\s*\]?\s*(?:Exp(?:ediente)?\.?)?.*$",
        "",
        contenido,
    )
    contenido = re.sub(
        r"(?im)^\s*(?:Nota|Aviso|Disclaimer|Descargo de responsabilidad)\s*:.*$",
        "",
        contenido,
    )
    contenido = re.sub(r"\[N\d+\]", "", contenido)
    contenido = re.sub(r"[ \t]+([,.;:!?])", r"\1", contenido)
    contenido = re.sub(r"[ \t]{2,}", " ", contenido)
    contenido = re.sub(r"\n{3,}", "\n\n", contenido)
    return contenido.strip()


class LexiView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        chats=None,
        on_list_chats=None,
        on_create_chat=None,
        on_load_messages=None,
        on_save_message=None,
        on_ask=None,
        on_summarize=None,
        on_open_expediente=None,
        **kwargs,
    ):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.on_list_chats = on_list_chats
        self.on_create_chat = on_create_chat
        self.on_load_messages = on_load_messages
        self.on_save_message = on_save_message
        self.on_ask = on_ask
        self.on_summarize = on_summarize
        self.on_open_expediente = on_open_expediente
        self.chats = list(chats or [])
        self.chat_id = None
        self.messages_data = []
        self._labels_mensajes = []
        self._en_proceso = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_history()
        self._build_conversation()
        self._render_chats()
        self._render_messages()

    def _build_history(self):
        self.history = ctk.CTkFrame(
            self, width=265, fg_color=C["sidebar"], corner_radius=0,
            border_width=1, border_color=C["border_soft"],
        )
        self.history.grid(row=0, column=0, sticky="nsew")
        self.history.grid_propagate(False)
        self.history.grid_columnconfigure(0, weight=1)
        self.history.grid_rowconfigure(5, weight=1)

        brand = ctk.CTkFrame(self.history, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(20, 16))
        brand.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            brand, text="✦", font=fuente(24, "bold"), text_color=C["violet"]
        ).grid(row=0, column=0, padx=(0, 9))
        ctk.CTkLabel(
            brand, text="LEXI", font=fuente(21, "bold"), text_color=C["text"],
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        self.btn_nueva = ctk.CTkButton(
            self.history, text="+  Nueva conversación", anchor="w", height=42,
            corner_radius=R.control, fg_color=C["card"], hover_color=C["card_hover"],
            text_color=C["text"], font=fuente(T.cuerpo, "bold"),
            command=self._nueva_conversacion,
        )
        self.btn_nueva.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 20))

        ctk.CTkLabel(
            self.history, text="RESUMEN INTELIGENTE", font=mono(T.etiqueta, "bold"),
            text_color=C["dim"], anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 6))
        resumen = ctk.CTkFrame(self.history, fg_color="transparent")
        resumen.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 14))
        resumen.grid_columnconfigure((0, 1, 2), weight=1, uniform="periodo")
        for columna, (dias, etiqueta) in enumerate(
            ((1, "24 h"), (7, "7 días"), (30, "30 días"))
        ):
            ctk.CTkButton(
                resumen, text=etiqueta, height=34, corner_radius=R.control,
                fg_color=C["card"], hover_color=C["card_hover"],
                text_color=C["text_soft"], font=fuente(T.meta, "bold"),
                command=lambda periodo=dias: self._iniciar_resumen(periodo),
            ).grid(row=0, column=columna, sticky="ew", padx=3)

        ctk.CTkLabel(
            self.history, text="CONVERSACIONES", font=mono(T.etiqueta, "bold"),
            text_color=C["dim"], anchor="w",
        ).grid(row=4, column=0, sticky="new", padx=18, pady=(0, 8))
        self.lista_chats = ctk.CTkScrollableFrame(
            self.history, fg_color="transparent", corner_radius=0,
        )
        self.lista_chats.grid(row=5, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.lista_chats.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.history, text="Consultas y fuentes permanecen en este equipo.",
            font=fuente(T.etiqueta), text_color=C["dim"], justify="left",
            wraplength=220,
        ).grid(row=6, column=0, sticky="ew", padx=18, pady=(8, 18))

    def _build_conversation(self):
        self.conversation = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self.conversation.grid(row=0, column=1, sticky="nsew")
        self.conversation.grid_columnconfigure(0, weight=1)
        self.conversation.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(
            self.conversation, fg_color=C["bg"], corner_radius=0,
            border_width=1, border_color=C["border_soft"],
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self.titulo_chat = ctk.CTkLabel(
            header, text="Nueva conversación", font=fuente(T.seccion, "bold"),
            text_color=C["text"], anchor="w",
        )
        self.titulo_chat.grid(row=0, column=0, sticky="ew", padx=24, pady=(17, 2))
        ctk.CTkLabel(
            header, text="Asistente de expedientes · IA local con citas",
            font=fuente(T.meta), text_color=C["muted"], anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 15))

        self.mensajes = ctk.CTkScrollableFrame(
            self.conversation, fg_color="transparent", corner_radius=0,
        )
        self.mensajes.grid(row=1, column=0, sticky="nsew", padx=22, pady=(12, 8))
        self.mensajes.grid_columnconfigure(0, weight=1)
        self.mensajes.bind("<Configure>", self._ajustar_ancho_mensajes, add="+")

        composer = ctk.CTkFrame(self.conversation, fg_color=C["card"], corner_radius=16)
        composer.grid(row=2, column=0, sticky="ew", padx=24, pady=(6, 20))
        composer.grid_columnconfigure(0, weight=1)
        self.estado = ctk.CTkLabel(
            composer,
            text="IA local · las consultas usan actuaciones SAE guardadas en este equipo.",
            font=fuente(T.etiqueta), text_color=C["muted"], anchor="w",
            justify="left",
        )
        self.estado.grid(row=0, column=0, columnspan=2, sticky="ew",
                         padx=16, pady=(12, 4))
        self.entrada = ctk.CTkEntry(
            composer, height=48, corner_radius=12, border_width=1,
            border_color=C["border"], fg_color=C["field"], text_color=C["text"],
            placeholder_text="Escribe una consulta sobre tus expedientes...",
            font=fuente(T.cuerpo),
        )
        self.entrada.grid(row=1, column=0, sticky="ew", padx=(14, 8), pady=(4, 14))
        self.entrada.bind("<Return>", self._enviar_con_return)
        self.btn_enviar = ctk.CTkButton(
            composer, text="Enviar", width=100, height=46, corner_radius=R.control,
            fg_color=C["accent"], hover_color=C["accent_hover"],
            font=fuente(T.cuerpo, "bold"), command=self._enviar,
        )
        self.btn_enviar.grid(row=1, column=1, padx=(0, 14), pady=(4, 14))

    def _render_chats(self):
        for widget in self.lista_chats.winfo_children():
            widget.destroy()

        if not self.chats:
            ctk.CTkLabel(
                self.lista_chats, text="Todavía no hay conversaciones.",
                font=fuente(T.meta), text_color=C["dim"], justify="left",
                wraplength=205,
            ).grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        for row, chat in enumerate(self.chats):
            activo = chat["id"] == self.chat_id
            titulo = chat["titulo"]
            if len(titulo) > 29:
                titulo = titulo[:28].rstrip() + "…"
            ctk.CTkButton(
                self.lista_chats,
                text=titulo,
                anchor="w", height=48, corner_radius=R.control,
                fg_color=C["accent_soft"] if activo else "transparent",
                hover_color=C["card"], text_color=C["text_soft"],
                font=fuente(T.meta),
                command=lambda chat_id=chat["id"]: self._abrir_chat(chat_id),
            ).grid(row=row, column=0, sticky="ew", padx=2, pady=2)

    def _render_messages(self):
        for widget in self.mensajes.winfo_children():
            widget.destroy()
        self._labels_mensajes = []

        if not self.messages_data:
            self._render_bienvenida()
            return

        row = 0
        for message in self.messages_data:
            es_usuario = message["rol"] == "user"
            linea = ctk.CTkFrame(self.mensajes, fg_color="transparent")
            linea.grid(row=row, column=0, sticky="ew", pady=7)
            linea.grid_columnconfigure(0, weight=1)
            burbuja = ctk.CTkFrame(
                linea,
                fg_color=C["accent_soft"] if es_usuario else C["card"],
                corner_radius=14,
            )
            burbuja.grid(
                row=0, column=0, sticky="e" if es_usuario else "w",
                padx=(70, 0) if es_usuario else (0, 70),
            )
            etiqueta = ctk.CTkLabel(
                burbuja, text=_contenido_visible(message["contenido"]),
                font=fuente(T.cuerpo),
                text_color=C["text"], justify="left", anchor="w",
                wraplength=max(self.mensajes.winfo_width() - 150, 300),
            )
            etiqueta.grid(row=0, column=0, padx=16, pady=12, sticky="w")
            self._labels_mensajes.append(etiqueta)
            row += 1

    def _ajustar_ancho_mensajes(self, event):
        wraplength = max(min(event.width - 150, 720), 300)
        for etiqueta in self._labels_mensajes:
            etiqueta.configure(wraplength=wraplength)

    def _render_bienvenida(self):
        bienvenida = ctk.CTkFrame(self.mensajes, fg_color="transparent")
        bienvenida.grid(row=0, column=0, sticky="ew", padx=24, pady=(48, 20))
        bienvenida.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            bienvenida, text="✦", font=fuente(36, "bold"), text_color=C["violet"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        ctk.CTkLabel(
            bienvenida, text="Hola, soy LEXI", font=fuente(29, "bold"),
            text_color=C["text"], anchor="w",
        ).grid(row=1, column=0, sticky="w")
        ctk.CTkLabel(
            bienvenida,
            text="Tu espacio para consultar y organizar la información de tus expedientes.",
            font=fuente(T.item), text_color=C["muted"], anchor="w",
            justify="left", wraplength=620,
        ).grid(row=2, column=0, sticky="w", pady=(5, 22))
        for row, sugerencia in enumerate(CONSULTAS_SUGERIDAS, start=3):
            ctk.CTkButton(
                bienvenida, text=sugerencia, anchor="w", height=42,
                corner_radius=R.control, fg_color=C["card"], hover_color=C["card_hover"],
                text_color=C["text_soft"], font=fuente(T.meta),
                command=lambda texto=sugerencia: self._usar_sugerencia(texto),
            ).grid(row=row, column=0, sticky="w", pady=4)

    def _usar_sugerencia(self, texto):
        self.entrada.delete(0, "end")
        self.entrada.insert(0, texto)
        self.entrada.focus_set()

    def _nueva_conversacion(self):
        try:
            chat_id = self.on_create_chat()
            self.chat_id = chat_id
            self.messages_data = []
            self.chats = self.on_list_chats()
        except (OSError, sqlite3.Error, ValueError, LookupError) as exc:
            self.estado.configure(
                text=f"No se pudo crear la conversación: {exc}",
                text_color=C["error"],
            )
            return

        self.titulo_chat.configure(text="Nueva conversación")
        self.estado.configure(
            text="IA local · las consultas y sus fuentes permanecen en este equipo.",
            text_color=C["muted"],
        )
        self._render_chats()
        self._render_messages()
        self.entrada.focus_set()

    def _abrir_chat(self, chat_id):
        try:
            mensajes = self.on_load_messages(chat_id)
            chats = self.on_list_chats()
        except (OSError, sqlite3.Error, ValueError, LookupError) as exc:
            self.estado.configure(
                text=f"No se pudo abrir la conversación: {exc}",
                text_color=C["error"],
            )
            return

        self.chat_id = chat_id
        self.messages_data = mensajes
        chat = next((item for item in chats if item["id"] == chat_id), None)
        if chat is None:
            self.estado.configure(
                text="No se encontró la conversación en el historial.",
                text_color=C["error"],
            )
            return
        self.chats = chats
        self.titulo_chat.configure(text=chat["titulo"])
        self.estado.configure(
            text="IA local · las consultas y sus fuentes permanecen en este equipo.",
            text_color=C["muted"],
        )
        self._render_chats()
        self._render_messages()

    def _enviar_con_return(self, event):
        if event.widget is self.entrada:
            self._enviar()
        return "break"

    def _enviar(self):
        contenido = self.entrada.get().strip()
        if not contenido or self._en_proceso:
            return

        try:
            if self.chat_id is None:
                self.chat_id = self.on_create_chat()
            self.on_save_message(self.chat_id, "user", contenido)
            self.messages_data = self.on_load_messages(self.chat_id)
            self.chats = self.on_list_chats()
        except (OSError, sqlite3.Error, ValueError, LookupError) as exc:
            self.estado.configure(
                text=f"No se pudo guardar la consulta: {exc}",
                text_color=C["error"],
            )
            return

        chat = next((item for item in self.chats if item["id"] == self.chat_id), None)
        if chat is None:
            self.estado.configure(text="No se encontró la conversación creada.",
                                  text_color=C["error"])
            return
        self.titulo_chat.configure(text=chat["titulo"])
        self.entrada.delete(0, "end")
        self._render_chats()
        self._render_messages()
        if not self.on_ask:
            self.estado.configure(text="No está configurado el servicio IA local.",
                                  text_color=C["error"])
            return
        self._en_proceso = True
        self.btn_nueva.configure(state="disabled")
        self.btn_enviar.configure(state="disabled", text="Consultando...")
        self.estado.configure(text="LEXI está consultando las actuaciones locales...",
                              text_color=C["cyan"])
        chat_id = self.chat_id
        self.on_ask(
            chat_id, contenido,
            lambda resultado, error: self._consulta_terminada(
                chat_id, resultado, error),
        )

    def _iniciar_resumen(self, periodo_dias):
        if self._en_proceso:
            return
        if not self.on_summarize:
            self.estado.configure(text="No está configurado el resumen IA local.",
                                  text_color=C["error"])
            return
        try:
            if self.chat_id is None:
                self.chat_id = self.on_create_chat()
                self.chats = self.on_list_chats()
                self._render_chats()
        except (OSError, sqlite3.Error, ValueError, LookupError) as exc:
            self.estado.configure(text=f"No se pudo iniciar el resumen: {exc}",
                                  text_color=C["error"])
            return
        self._en_proceso = True
        self.btn_nueva.configure(state="disabled")
        self.btn_enviar.configure(state="disabled", text="Analizando...")
        periodo = "las últimas 24 horas" if periodo_dias == 1 else (
            f"los últimos {periodo_dias} días")
        self.estado.configure(
            text=f"Analizando actuaciones incorporadas en {periodo}...",
            text_color=C["cyan"],
        )
        chat_id = self.chat_id
        self.on_summarize(
            chat_id, periodo_dias,
            lambda resultado, error: self._consulta_terminada(
                chat_id, resultado, error),
        )

    def _consulta_terminada(self, chat_id, resultado, error):
        self._en_proceso = False
        self.btn_nueva.configure(state="normal")
        self.btn_enviar.configure(state="normal", text="Enviar")
        if error:
            self.estado.configure(text=f"No se pudo completar la consulta: {error}",
                                  text_color=C["error"])
        elif resultado and "findings" in resultado and resultado.get("findings"):
            self.estado.configure(
                text=(
                    "Análisis listo. Las fechas sugeridas siguen pendientes: "
                    "revísalas y confírmalas desde el calendario."
                ),
                text_color=C["warn"],
            )
        elif resultado and "findings" in resultado:
            self.estado.configure(text="Resumen local guardado con sus fuentes.",
                                  text_color=C["ok"])
        elif resultado and resultado.get("scheduled_event"):
            self.estado.configure(
                text="Evento agregado al calendario.",
                text_color=C["ok"],
            )
        else:
            self.estado.configure(text="Respuesta local guardada con sus fuentes.",
                                  text_color=C["ok"])
        try:
            self.chats = self.on_list_chats()
            if self.chat_id == chat_id:
                self.messages_data = self.on_load_messages(chat_id)
                chat = next((item for item in self.chats if item["id"] == chat_id), None)
                if chat:
                    self.titulo_chat.configure(text=chat["titulo"])
                self._render_chats()
                self._render_messages()
        except (OSError, sqlite3.Error, ValueError, LookupError) as exc:
            self.estado.configure(text=f"La respuesta terminó, pero no se pudo cargar: {exc}",
                                  text_color=C["error"])

    def actualizar_chats(self, chats):
        self.chats = list(chats)
        self._render_chats()
