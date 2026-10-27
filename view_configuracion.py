"""
LexBot - Vista Configuración: credenciales del SAE y opciones del bot.

Las credenciales se guardan con Windows Credential Manager y la conexión se
prueba directamente contra el portal oficial.
"""

import sqlite3

import customtkinter as ctk

import ajustes
import database
from credential_store import guardar_credenciales, leer_credenciales
from theme import C, R, S, T, aplicar_escala, fuente, mono
from widgets import HAY_PILLOW, Avatar

POR_DEFECTO_NOMBRE = "Profesional sin nombre"

FRECUENCIAS = [
    "Cada 1 hora",
    "Cada 3 horas",
    "Cada 6 horas",
    "Una vez al día",
    "Solo manualmente",
]

NIVELES_IA = [
    "Breve (solo la acción a realizar)",
    "Estándar (acción, plazo y fundamento)",
    "Detallado (incluye texto citado del proveído)",
]


class Section(ctk.CTkFrame):
    def __init__(self, master, titulo, descripcion=None):
        super().__init__(master, fg_color=C["card"], corner_radius=R.tarjeta,
                         border_width=1, border_color=C["border"])
        self.grid_columnconfigure(0, weight=1)
        row = 0

        ctk.CTkLabel(self, text=titulo, font=fuente(T.seccion, "bold"),
                     text_color=C["text"], anchor="w"
                     ).grid(row=row, column=0, sticky="ew", padx=22, pady=(18, 2))
        row += 1

        if descripcion:
            self.desc = ctk.CTkLabel(self, text=descripcion, font=fuente(T.meta),
                                     text_color=C["muted"], anchor="w", justify="left")
            self.desc.grid(row=row, column=0, sticky="ew", padx=22, pady=(0, 10))
            row += 1
            self.bind("<Configure>",
                      lambda e: self.desc.configure(wraplength=max(e.width - 60, 240)), add="+")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=row, column=0, sticky="ew", padx=22, pady=(4, 20))
        self.body.grid_columnconfigure(0, weight=1)


class LabeledEntry(ctk.CTkFrame):
    def __init__(self, master, etiqueta, placeholder="", secreto=False):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=etiqueta.upper(), font=mono(T.etiqueta, "bold"),
                     text_color=C["muted"], anchor="w"
                     ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        self.entry = ctk.CTkEntry(self, height=40, corner_radius=10, border_width=0,
                                  fg_color=C["field"], text_color=C["text"],
                                  placeholder_text=placeholder, font=fuente(T.cuerpo),
                                  show="•" if secreto else "")
        self.entry.grid(row=1, column=0, sticky="ew")

        if secreto:
            self.toggle = ctk.CTkButton(self, text="Mostrar", width=84, height=40,
                                        corner_radius=10, fg_color=C["field"],
                                        hover_color=C["card_hover"], text_color=C["muted"],
                                        font=fuente(T.meta), command=self._toggle)
            self.toggle.grid(row=1, column=1, padx=(8, 0))

    def _toggle(self):
        visible = self.entry.cget("show") == ""
        self.entry.configure(show="•" if visible else "")
        self.toggle.configure(text="Mostrar" if visible else "Ocultar")

    def get(self):
        return self.entry.get()

    def set(self, valor):
        self.entry.delete(0, "end")
        self.entry.insert(0, valor)


class ConfiguracionView(ctk.CTkFrame):
    def __init__(self, master, on_save=None, on_test=None, on_perfil=None, **kwargs):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.on_save = on_save
        self.on_test = on_test
        self.on_perfil = on_perfil

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.grid(row=0, column=0, sticky="ew", padx=S.xl, pady=(S.xl, S.md))
        encabezado.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(encabezado, text="Configuración",
                     font=fuente(T.titulo_pagina, "bold"),
                     text_color=C["text"], anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(encabezado, text="Cuenta, apariencia y comportamiento del barrido",
                     font=fuente(T.meta), text_color=C["muted"], anchor="w"
                     ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=S.xl)
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_perfil()
        self._build_apariencia()
        self._build_credenciales()
        self._build_frecuencia()
        self._build_preferencias()
        self._build_footer()

    # --- Perfil del profesional --------------------------------------------
    def _build_perfil(self):
        datos = ajustes.cargar()
        sec = Section(self.scroll, "Datos del profesional",
                      "Se muestran en la barra lateral de la aplicación.")
        sec.grid(row=0, column=0, sticky="ew", pady=(0, S.md))
        b = sec.body
        # Section deja la columna 0 con peso: acá el espacio sobrante tiene
        # que ir a los campos, no a la columna del avatar.
        b.grid_columnconfigure(0, weight=0)
        b.grid_columnconfigure(1, weight=1)

        self.avatar_previa = Avatar(b, iniciales=ajustes.iniciales(datos.get("nombre")),
                                    foto=datos.get("foto", ""), lado=64)
        self.avatar_previa.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, S.lg))

        campos = ctk.CTkFrame(b, fg_color="transparent")
        campos.grid(row=0, column=1, sticky="ew")
        campos.grid_columnconfigure(0, weight=1)

        self.in_nombre = LabeledEntry(campos, "Nombre y apellido",
                                      placeholder="Dra. Ana Gómez")
        self.in_nombre.grid(row=0, column=0, sticky="ew", pady=(0, S.md))
        self.in_nombre.set(datos.get("nombre", ""))

        self.in_matricula = LabeledEntry(campos, "Matrícula",
                                         placeholder="T° XIV F° 208 · C.P.A.T.")
        self.in_matricula.grid(row=1, column=0, sticky="ew", pady=(0, S.md))
        self.in_matricula.set(datos.get("matricula", ""))

        self.in_foto = LabeledEntry(campos, "Ruta de la foto (opcional)",
                                    placeholder=r"C:\Users\...\foto.jpg")
        self.in_foto.grid(row=2, column=0, sticky="ew")
        self.in_foto.set(datos.get("foto", ""))

        self.aviso_foto = ctk.CTkLabel(
            b,
            text=("La foto es opcional: sin foto se muestran tus iniciales. "
                  "Para usarla hace falta la librería Pillow (pip install pillow)."
                  if not HAY_PILLOW else
                  "La foto es opcional: sin foto se muestran tus iniciales."),
            font=fuente(T.meta), text_color=C["muted"], anchor="w", justify="left")
        self.aviso_foto.grid(row=1, column=1, sticky="ew", pady=(S.md, 0))

        ctk.CTkButton(b, text="Aplicar datos del profesional", height=40,
                      corner_radius=R.control, fg_color=C["accent"],
                      hover_color=C["accent_hover"], font=fuente(T.meta, "bold"),
                      command=self._guardar_perfil
                      ).grid(row=2, column=1, sticky="w", pady=(S.md, 0))

        b.bind("<Configure>",
               lambda e: self.aviso_foto.configure(wraplength=max(e.width - 110, 240)),
               add="+")

    def _guardar_perfil(self):
        nombre = self.in_nombre.get().strip() or POR_DEFECTO_NOMBRE
        ajustes.guardar(nombre=nombre,
                        matricula=self.in_matricula.get().strip(),
                        foto=self.in_foto.get().strip())
        # Se redibuja la previsualización con los datos nuevos.
        self.avatar_previa.destroy()
        datos = ajustes.cargar()
        self.avatar_previa = Avatar(self.in_nombre.master.master,
                                    iniciales=ajustes.iniciales(datos["nombre"]),
                                    foto=datos.get("foto", ""), lado=64)
        self.avatar_previa.grid(row=0, column=0, rowspan=3, sticky="nw", padx=(0, S.lg))
        if self.on_perfil:
            self.on_perfil()
        self._avisar("Datos del profesional actualizados")

    # --- Apariencia ---------------------------------------------------------
    def _build_apariencia(self):
        sec = Section(self.scroll, "Apariencia",
                      "El tamaño afecta tipografía y controles a la vez, "
                      "y se aplica al instante.")
        sec.grid(row=1, column=0, sticky="ew", pady=(0, S.md))
        b = sec.body

        ctk.CTkLabel(b, text="TAMAÑO DE LA INTERFAZ", font=mono(T.etiqueta, "bold"),
                     text_color=C["muted"], anchor="w"
                     ).grid(row=0, column=0, sticky="ew", pady=(0, S.sm))

        self.var_escala = ctk.StringVar(value=ajustes.cargar().get("escala"))
        ctk.CTkSegmentedButton(
            b, values=list(ajustes.ESCALAS.keys()), variable=self.var_escala,
            height=42, corner_radius=R.control, font=fuente(T.meta),
            fg_color=C["field"], selected_color=C["accent"],
            selected_hover_color=C["accent_hover"], unselected_color=C["field"],
            unselected_hover_color=C["card_hover"], text_color=C["text"],
            command=self._cambiar_escala).grid(row=1, column=0, sticky="w")

        self.muestra = ctk.CTkLabel(
            b, text="Exp. 10452/2026 · Vence el martes 20/10/2026",
            font=mono(T.cuerpo), text_color=C["text_soft"], anchor="w")
        self.muestra.grid(row=2, column=0, sticky="ew", pady=(S.md, 0))

        self.estado_escala = ctk.CTkLabel(b, text="", font=fuente(T.meta),
                                          text_color=C["ok"], anchor="w")
        self.estado_escala.grid(row=3, column=0, sticky="ew", pady=(S.sm, 0))

    def _cambiar_escala(self, valor):
        aplicar_escala(valor)
        self.estado_escala.configure(text=f"Tamaño {valor.lower()} aplicado y guardado")
        self.after(2500, lambda: self.estado_escala.configure(text=""))

    def _build_credenciales(self):
        sec = Section(self.scroll, "Credenciales de Acceso al SAE (Poder Judicial)",
                      "Se usan únicamente para iniciar sesión en el portal desde este equipo.")
        sec.grid(row=2, column=0, sticky="ew", pady=(0, S.md))
        b = sec.body

        self.in_usuario = LabeledEntry(b, "CUIT / Usuario", placeholder="20-12345678-9")
        self.in_usuario.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        self.in_password = LabeledEntry(b, "Contraseña", placeholder="••••••••", secreto=True)
        self.in_password.grid(row=1, column=0, sticky="ew", pady=(0, 14))

        nota = ctk.CTkFrame(b, fg_color=C["field"], corner_radius=10)
        nota.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        nota.grid_columnconfigure(1, weight=1)
        # height=1: sin alto explícito el CTkFrame reservaría 200 px.
        ctk.CTkFrame(nota, width=4, height=1, fg_color=C["accent"], corner_radius=2).grid(
            row=0, column=0, sticky="ns", padx=(10, 0), pady=12)
        nota_label = ctk.CTkLabel(
            nota,
            text=("Tus credenciales se guardan en Windows Credential Manager, protegidas "
                  "por el sistema operativo. LexBot solo las envía al portal oficial del "
                  "Poder Judicial para iniciar sesión."),
            font=fuente(T.meta), text_color=C["muted"], anchor="w", justify="left")
        nota_label.grid(row=0, column=1, sticky="ew", padx=12, pady=12)
        nota.bind("<Configure>",
                  lambda e: nota_label.configure(wraplength=max(e.width - 60, 220)))

        acciones = ctk.CTkFrame(b, fg_color="transparent")
        acciones.grid(row=3, column=0, sticky="ew")
        acciones.grid_columnconfigure(1, weight=1)

        self.btn_test = ctk.CTkButton(
            acciones, text="Probar Conexión con el SAE", height=40, corner_radius=10,
            fg_color=C["accent"], hover_color=C["accent_hover"],
            font=fuente(T.cuerpo, "bold"), command=self._probar_conexion)
        self.btn_test.grid(row=0, column=0)

        self.estado_conexion = ctk.CTkLabel(acciones, text="Sin probar",
                                            font=mono(T.meta),
                                            text_color=C["muted"], anchor="w")
        self.estado_conexion.grid(row=0, column=1, sticky="w", padx=14)
        try:
            credenciales = leer_credenciales()
        except (OSError, ValueError) as exc:
            self.estado_conexion.configure(
                text=f"Almacén de credenciales no disponible: {exc}",
                text_color=C["error"],
            )
        else:
            if credenciales:
                self.in_usuario.set(credenciales["cuit"])
                self.in_password.set(credenciales["password"])

    def _build_frecuencia(self):
        sec = Section(self.scroll, "Frecuencia de Sincronización Automática",
                      "Define cada cuánto LexBot revisa el portal en busca de novedades.")
        sec.grid(row=3, column=0, sticky="ew", pady=(0, S.md))
        b = sec.body

        ctk.CTkLabel(b, text="INTERVALO DE BARRIDO", font=mono(T.etiqueta, "bold"),
                     text_color=C["muted"], anchor="w"
                     ).grid(row=0, column=0, sticky="ew", pady=(0, 4))

        frecuencia = database.leer_preferencias().get("frecuencia", FRECUENCIAS[1])
        if frecuencia not in FRECUENCIAS:
            frecuencia = FRECUENCIAS[1]
        self.var_frecuencia = ctk.StringVar(value=frecuencia)
        ctk.CTkOptionMenu(
            b, values=FRECUENCIAS, variable=self.var_frecuencia, height=40, width=280,
            corner_radius=10, fg_color=C["field"], button_color=C["field"],
            button_hover_color=C["card_hover"], text_color=C["text"],
            dropdown_fg_color=C["card"], dropdown_text_color=C["text"],
            dropdown_hover_color=C["card_hover"], font=fuente(T.cuerpo),
            command=self._on_frecuencia).grid(row=1, column=0, sticky="w")

        self.aviso_frecuencia = ctk.CTkLabel(b, text="", font=fuente(T.meta),
                                             text_color=C["warn"], anchor="w", justify="left")
        self.aviso_frecuencia.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self._on_frecuencia(self.var_frecuencia.get())

    def _on_frecuencia(self, valor):
        if valor == "Cada 1 hora":
            self.aviso_frecuencia.configure(
                text=("Un barrido por hora genera muchas consultas al portal. "
                      "Conviene usarlo solo si tenés pocos expedientes activos."))
        else:
            self.aviso_frecuencia.configure(text="")

    def _build_preferencias(self):
        sec = Section(self.scroll, "Preferencias de Notificaciones y IA")
        sec.grid(row=4, column=0, sticky="ew", pady=(0, S.md))
        b = sec.body

        ctk.CTkLabel(b, text="NOTIFICACIONES", font=mono(T.etiqueta, "bold"),
                     text_color=C["muted"], anchor="w"
                     ).grid(row=0, column=0, sticky="ew", pady=(0, 6))

        preferencias = database.leer_preferencias()
        self.var_alertas_escritorio = ctk.BooleanVar(
            value=preferencias.get("alertas_escritorio", True))
        self.var_alertas_vencimiento = ctk.BooleanVar(
            value=preferencias.get("alertas_vencimiento", True))
        self.var_alertas_inactividad = ctk.BooleanVar(
            value=preferencias.get("alertas_inactividad", False))

        checks = [
            (self.var_alertas_escritorio, "Mostrar alertas de escritorio al terminar un barrido"),
            (self.var_alertas_vencimiento, "Avisar cuando un plazo venza dentro de 48 horas"),
            (self.var_alertas_inactividad, "Avisar sobre expedientes sin movimientos"),
        ]
        for i, (var, texto) in enumerate(checks, start=1):
            ctk.CTkCheckBox(b, text=texto, variable=var, font=fuente(T.cuerpo),
                            text_color=C["text"], fg_color=C["accent"],
                            hover_color=C["accent_hover"], border_color=C["muted"],
                            corner_radius=6, checkbox_width=20, checkbox_height=20
                            ).grid(row=i, column=0, sticky="w", pady=4)

        ctk.CTkLabel(b, text="RESUMEN GENERADO POR IA",
                     font=mono(T.etiqueta, "bold"), text_color=C["muted"], anchor="w"
                     ).grid(row=5, column=0, sticky="ew", pady=(16, 4))

        nivel_ia = preferencias.get("nivel_ia", NIVELES_IA[1])
        if nivel_ia not in NIVELES_IA:
            nivel_ia = NIVELES_IA[1]
        self.var_nivel_ia = ctk.StringVar(value=nivel_ia)
        ctk.CTkOptionMenu(
            b, values=NIVELES_IA, variable=self.var_nivel_ia, height=40, width=380,
            corner_radius=10, fg_color=C["field"], button_color=C["field"],
            button_hover_color=C["card_hover"], text_color=C["text"],
            dropdown_fg_color=C["card"], dropdown_text_color=C["text"],
            dropdown_hover_color=C["card_hover"], font=fuente(T.cuerpo)
        ).grid(row=6, column=0, sticky="w")

        self.var_mostrar_fuente = ctk.BooleanVar(
            value=preferencias.get("mostrar_fuente", True))
        ctk.CTkCheckBox(b, text="Mostrar siempre el texto original junto al resumen",
                        variable=self.var_mostrar_fuente, font=fuente(T.cuerpo),
                        text_color=C["text"], fg_color=C["accent"],
                        hover_color=C["accent_hover"], border_color=C["muted"],
                        corner_radius=6, checkbox_width=20, checkbox_height=20
                        ).grid(row=7, column=0, sticky="w", pady=(12, 0))

        aviso = ctk.CTkLabel(
            b, text=("Los resúmenes y las fechas calculadas son orientativos. "
                     "Verificá siempre el proveído original antes de actuar."),
            font=fuente(T.meta), text_color=C["warn"], anchor="w", justify="left")
        aviso.grid(row=8, column=0, sticky="ew", pady=(10, 0))
        b.bind("<Configure>",
               lambda e: aviso.configure(wraplength=max(e.width - 20, 240)), add="+")

    def _build_footer(self):
        pie = ctk.CTkFrame(self.scroll, fg_color="transparent")
        pie.grid(row=5, column=0, sticky="ew", pady=(S.sm, S.xl))
        pie.grid_columnconfigure(0, weight=1)

        self.estado_guardado = ctk.CTkLabel(pie, text="", font=fuente(T.meta),
                                            text_color=C["ok"], anchor="w")
        self.estado_guardado.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(pie, text="Guardar cambios", height=42, width=170, corner_radius=10,
                      fg_color=C["accent"], hover_color=C["accent_hover"],
                      font=fuente(T.item, "bold"), command=self._guardar
                      ).grid(row=0, column=1, sticky="e")

    def valores(self):
        """Configuración actual, sin la contraseña."""
        return {
            "usuario": self.in_usuario.get(),
            "frecuencia": self.var_frecuencia.get(),
            "alertas_escritorio": self.var_alertas_escritorio.get(),
            "alertas_vencimiento": self.var_alertas_vencimiento.get(),
            "alertas_inactividad": self.var_alertas_inactividad.get(),
            "nivel_ia": self.var_nivel_ia.get(),
            "mostrar_fuente": self.var_mostrar_fuente.get(),
        }

    def _probar_conexion(self):
        usuario, password = self.in_usuario.get().strip(), self.in_password.get()
        if not usuario or not password:
            self.estado_conexion.configure(text="Completá usuario y contraseña",
                                           text_color=C["error"])
            return

        self.btn_test.configure(state="disabled", text="Probando...")
        self.estado_conexion.configure(text="Conectando al portal...", text_color=C["muted"])

        if self.on_test:
            self.on_test(usuario, password, self._resultado_prueba)
        else:
            self._resultado_prueba(False, "No se configuró el conector del SAE.")

    def _resultado_prueba(self, resultado, mensaje=""):
        self.btn_test.configure(state="normal", text="Probar Conexión con el SAE")
        if hasattr(resultado, "exito"):
            exito, estado, mensaje = resultado.exito, resultado.estado, resultado.mensaje
        else:
            exito, estado = bool(resultado), ("Éxito" if resultado else "Error")
        if exito:
            try:
                guardar_credenciales(self.in_usuario.get().strip(), self.in_password.get())
            except (OSError, ValueError) as exc:
                self.estado_conexion.configure(
                    text=f"Conexión válida; no se guardaron las credenciales: {exc}",
                    text_color=C["warn"],
                )
                return
        self.estado_conexion.configure(
            text=f"{estado}: {mensaje}" if mensaje else estado,
            text_color=C["ok"] if exito else C["error"],
        )

    def _avisar(self, texto):
        self.estado_guardado.configure(text=texto)
        self.after(2500, lambda: self.estado_guardado.configure(text=""))

    def _guardar(self):
        try:
            if self.on_save:
                self.on_save(self.valores(), self.in_password.get())
            if self.in_usuario.get().strip() and self.in_password.get():
                guardar_credenciales(self.in_usuario.get().strip(), self.in_password.get())
        except (OSError, sqlite3.Error, ValueError) as exc:
            self.estado_guardado.configure(
                text=f"No se pudieron guardar los cambios: {exc}",
                text_color=C["error"],
            )
            return
        self._avisar("Preferencias guardadas localmente.")
