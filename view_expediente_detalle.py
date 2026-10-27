"""
LexBot - Vista de detalle de un expediente.

Es la pantalla donde el abogado deja de leer el portal: resumen de la última
novedad, actuaciones con fojas, documentos descargados, partes y juzgado.

Nomenclatura del Poder Judicial de Tucumán: los juzgados se identifican por
nominación (IIIª Nominación) y centro judicial (Capital, Concepción,
Monteros), no por número como en el fuero nacional.

La vista presenta únicamente datos recibidos del SAE. Los plazos deben verificarse en el portal.
"""

import customtkinter as ctk

from theme import C, R, T, barra_acento, fuente, mono

def _completar(expediente):
    expediente = expediente or {}
    actuaciones = list(expediente.get("actuaciones", []))
    return {
        "expediente": expediente.get("expediente", ""),
        "caratula": expediente.get("caratula", "Sin caratula informada"),
        "fuero": expediente.get("fuero", "Fuero no informado"),
        "juzgado": expediente.get("juzgado", "Juzgado no informado"),
        "oficina": expediente.get("oficina", ""),
        "centro": expediente.get("centro_judicial", ""),
        "secretaria": "",
        "estado_sae": expediente.get("estado", "No informado"),
        "sincronizado": expediente.get("actualizado_en", "Sin sincronizacion registrada"),
        "cedulas": sum("cedula" in act.get("tipo", "").lower() for act in actuaciones),
        "monto": "No informado por el SAE",
        "plazo_proximo": "No calculado",
        "etapa": "No informada",
        "novedad": actuaciones[0] if actuaciones else None,
        "partes": [],
        "funcionarios": [],
        "actuaciones": actuaciones,
        "pdfs": [],
        "agenda": [],
    }


def _vista_previa_actuacion(actuacion):
    texto = (
        actuacion.get("titulo")
        if actuacion.get("texto_completo")
        else actuacion.get("texto") or actuacion.get("titulo", "")
    )
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= 240 else texto[:237].rstrip() + "..."


def _formatear_texto_actuacion(texto):
    lineas = []
    for linea in str(texto or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        linea = " ".join(linea.split())
        if not linea:
            if lineas and lineas[-1]:
                lineas.append("")
            continue
        lineas.append(linea)
    while lineas and not lineas[-1]:
        lineas.pop()
    return "\n".join(lineas)


def _resumen_texto_actuacion(texto, max_caracteres=480, max_lineas=8):
    texto_formateado = _formatear_texto_actuacion(texto)
    lineas = texto_formateado.splitlines()
    truncado = len(lineas) > max_lineas
    resumen = "\n".join(lineas[:max_lineas])
    if len(resumen) > max_caracteres:
        resumen = resumen[:max_caracteres - 3].rsplit(" ", 1)[0].rstrip()
        truncado = True
    if truncado:
        resumen = resumen.rstrip() + "..."
    return resumen


def _clasificar_linea_actuacion(texto, primera_linea=False):
    normalizado = texto.casefold()
    marcas_final = (
        "firmado", "firma digital", "fdo.", "juez", "jueza", "secretario",
        "secretaria", "es justicia", "notifíquese", "notifiquese",
    )
    if any(marca in normalizado for marca in marcas_final):
        return "final"
    letras = [caracter for caracter in texto if caracter.isalpha()]
    if len(texto) <= 110 and letras and texto == texto.upper():
        return "titulo" if primera_linea else "subtitulo"
    return "parrafo"


PESTANAS = ["Información general", "Movimientos", "Documentos", "Agenda del caso"]


# ---------------------------------------------------------------------------
# Piezas reutilizables
# ---------------------------------------------------------------------------
def _chip(master, texto, color_texto=None, color_fondo=None):
    return ctk.CTkLabel(master, text=f" {texto} ",
                        fg_color=color_fondo or C["card_row"], corner_radius=R.chip,
                        height=29, text_color=color_texto or C["muted"],
                        font=mono(T.meta, "bold"))


class Tarjeta(ctk.CTkFrame):
    """Tarjeta con título, acento opcional y cuerpo listo para llenar."""

    def __init__(self, master, titulo, acento=None, extra=None):
        super().__init__(master, fg_color=C["card"], corner_radius=R.tarjeta,
                         border_width=1, border_color=C["border"])
        self.grid_columnconfigure(0, weight=1)
        fila = 0

        if acento:
            barra_acento(self, acento).grid(row=fila, column=0, sticky="ew",
                                            padx=16, pady=(12, 0))
            fila += 1

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.grid(row=fila, column=0, sticky="ew", padx=20, pady=(14, 10))
        cab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cab, text=titulo.upper(), font=fuente(T.seccion, "bold"),
                     text_color=C["text"], anchor="w").grid(row=0, column=0, sticky="w")
        if extra:
            ctk.CTkLabel(cab, text=extra, font=mono(T.etiqueta),
                         text_color=C["muted"], anchor="e").grid(row=0, column=1, sticky="e")
        fila += 1

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=fila, column=0, sticky="ew", padx=20, pady=(0, 18))
        self.body.grid_columnconfigure(0, weight=1)


class DatoCompacto(ctk.CTkFrame):
    """Rótulo arriba, valor abajo. Para las métricas de la cabecera."""

    def __init__(self, master, rotulo, valor, color=None):
        super().__init__(master, fg_color=C["card"], corner_radius=R.tarjeta,
                         border_width=1, border_color=C["border"])
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=rotulo.upper(), font=mono(T.etiqueta),
                     text_color=C["muted"], anchor="w"
                     ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 2))
        ctk.CTkLabel(self, text=valor, font=fuente(T.item, "bold"),
                     text_color=color or C["text"], anchor="w"
                     ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))


# ---------------------------------------------------------------------------
# Vista
# ---------------------------------------------------------------------------
class ExpedienteDetalleView(ctk.CTkFrame):
    def __init__(self, master, expediente=None, on_back=None,
                 on_ver_original=None, on_sync=None,
                 on_load_actuacion=None, on_open_expediente=None, **kwargs):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.datos = _completar(expediente)
        self.on_back = on_back
        self.on_ver_original = on_ver_original
        self.on_sync = on_sync
        self.on_load_actuacion = on_load_actuacion
        self.on_open_expediente = on_open_expediente
        self.lector_texto = None
        self.pestana = PESTANAS[0]
        self.botones_pestana = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_barra_superior()

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_encabezado()
        self._build_metricas()
        self._build_pestanas()

        self.contenido = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.contenido.grid(row=3, column=0, sticky="nsew")
        self.contenido.grid_columnconfigure(0, weight=1)
        self._render_pestana()

    # --- Barra superior -----------------------------------------------------
    def _build_barra_superior(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 12))
        barra.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(barra, text="←  Volver a expedientes", height=34, width=200,
                      corner_radius=R.control, fg_color=C["card"],
                      hover_color=C["card_hover"], text_color=C["text_soft"],
                      font=fuente(T.meta), command=self._volver
                      ).grid(row=0, column=0, sticky="w")

        acciones = ctk.CTkFrame(barra, fg_color="transparent")
        acciones.grid(row=0, column=2, sticky="e")
        acciones.grid_columnconfigure(1, weight=1)

        self.btn_actualizar = ctk.CTkButton(
            acciones, text="Actualizar desde el SAE", height=34, corner_radius=R.control,
            fg_color=C["accent"], hover_color=C["accent_hover"],
            font=fuente(T.meta, "bold"), command=self._actualizar)
        self.btn_actualizar.grid(row=0, column=0)
        self.estado_actualizacion = ctk.CTkLabel(
            acciones, text="", font=fuente(T.etiqueta), text_color=C["muted"])
        self.estado_actualizacion.grid(row=1, column=0, columnspan=2, sticky="e")

    # --- Encabezado ---------------------------------------------------------
    def _build_encabezado(self):
        d = self.datos
        cab = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        cab.grid_columnconfigure(0, weight=1)

        chips = ctk.CTkFrame(cab, fg_color="transparent")
        chips.grid(row=0, column=0, sticky="w", pady=(0, 8))
        for i, (texto, color) in enumerate([
            (f"EXP. {d['expediente']}", C["cyan"]),
            (d["fuero"].upper(), C["muted"]),
            (f"ESTADO SAE: {d['estado_sae'].upper()}", C["ok"]),
            (f"{d['cedulas']} CÉDULAS", C["muted"]),
        ]):
            _chip(chips, texto, color).grid(row=0, column=i, padx=(0 if i == 0 else 8, 0))

        self.titulo = ctk.CTkLabel(cab, text=d["caratula"], font=fuente(T.saludo, "bold"),
                                   text_color=C["text"], anchor="w", justify="left")
        self.titulo.grid(row=1, column=0, sticky="ew")

        ubicacion = " · ".join(
            valor for valor in (
                d["oficina"], d["juzgado"], d["centro"], d["secretaria"],
            ) if valor and valor != "Juzgado no informado"
        )
        self.sub = ctk.CTkLabel(
            cab, text=ubicacion,
            font=mono(16), text_color=C["text_soft"], anchor="w", justify="left")
        self.sub.grid(row=2, column=0, sticky="ew", pady=(4, 0))

        ctk.CTkLabel(cab, text=f"Sincronizado {d['sincronizado']}", font=mono(T.meta),
                     text_color=C["dim"], anchor="w").grid(row=3, column=0, sticky="w",
                                                           pady=(7, 0))

        cab.bind("<Configure>", self._ajustar_ancho, add="+")

    def _ajustar_ancho(self, event):
        ancho = max(event.width - 20, 300)
        self.titulo.configure(wraplength=ancho)
        self.sub.configure(wraplength=ancho)

    def _build_metricas(self):
        d = self.datos
        fila = ctk.CTkFrame(self.scroll, fg_color="transparent")
        fila.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        for i in range(4):
            fila.grid_columnconfigure(i, weight=1, uniform="met")

        datos = [
            ("Monto reclamado", d["monto"], C["text"]),
            ("Plazo más próximo", d["plazo_proximo"], C["warn"]),
            # El contador sale de la lista real, nunca de un número aparte:
            # así no puede quedar desactualizado respecto de lo descargado.
            ("Documentos", f"{len(d['pdfs'])} archivos", C["text"]),
            ("Etapa", d["etapa"], C["cyan"]),
        ]
        for col, (rotulo, valor, color) in enumerate(datos):
            DatoCompacto(fila, rotulo, valor, color).grid(
                row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 12, 0))

    # --- Pestañas -----------------------------------------------------------
    def _build_pestanas(self):
        barra = ctk.CTkFrame(self.scroll, fg_color="transparent")
        barra.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        barra.grid_columnconfigure(len(PESTANAS), weight=1)

        for i, nombre in enumerate(PESTANAS):
            btn = ctk.CTkButton(barra, text=nombre, height=34, corner_radius=R.control,
                                font=fuente(T.meta),
                                command=lambda n=nombre: self._cambiar_pestana(n))
            btn.grid(row=0, column=i, padx=(0 if i == 0 else 8, 0))
            self.botones_pestana[nombre] = btn
        self._estilo_pestanas()

    def _estilo_pestanas(self):
        for nombre, btn in self.botones_pestana.items():
            activa = nombre == self.pestana
            btn.configure(fg_color=C["accent"] if activa else C["card"],
                          hover_color=C["accent_hover"] if activa else C["card_hover"],
                          text_color=C["text"] if activa else C["text_soft"])

    def _cambiar_pestana(self, nombre):
        self.pestana = nombre
        self._estilo_pestanas()
        self._render_pestana()

    def _render_pestana(self):
        for w in self.contenido.winfo_children():
            w.destroy()
        # Cada pestaña define su propia grilla: hay que limpiar la anterior,
        # si no la de dos columnas deja la siguiente a media página.
        for col in (0, 1):
            self.contenido.grid_columnconfigure(col, weight=0, uniform="")
        if self.pestana == "Información general":
            self._tab_general()
        elif self.pestana == "Movimientos":
            self._tab_movimientos()
        elif self.pestana == "Documentos":
            self._tab_documentos()
        else:
            self._tab_agenda()

    # --- Pestaña: información general ---------------------------------------
    def _tab_general(self):
        for column in range(2):
            self.contenido.grid_columnconfigure(
                column, weight=1, uniform="general_columns")

        self._panel_novedad().grid(
            row=0, column=0, sticky="new", padx=(0, 8))
        columna_derecha = ctk.CTkFrame(
            self.contenido, fg_color="transparent")
        columna_derecha.grid(
            row=0, column=1, sticky="new", padx=(8, 0))
        columna_derecha.grid_columnconfigure(0, weight=1)
        self._panel_partes(columna_derecha).grid(
            row=0, column=0, sticky="ew")
        self._panel_juzgado(columna_derecha).grid(
            row=1, column=0, sticky="ew", pady=(10, 0))

    def _panel_novedad(self):
        n = self.datos["novedad"]
        card = Tarjeta(self.contenido, "Ultima actuacion importada", acento="alertas")
        card.body.grid_columnconfigure(0, weight=1)
        if not n:
            ctk.CTkLabel(
                card.body,
                text="Sin actuaciones registradas. Realiza un barrido del SAE.",
                font=fuente(T.cuerpo), text_color=C["muted"], anchor="w",
            ).grid(row=0, column=0, sticky="ew")
            return card

        ctk.CTkLabel(
            card.body, text=f"{n.get('tipo', 'Actuacion')} · {n.get('fecha', '')}",
            font=mono(T.etiqueta, "bold"), text_color=C["muted"], anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            card.body, text=n.get("titulo", ""), font=fuente(T.item, "bold"),
            text_color=C["text"], anchor="w", justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        texto_previo = _resumen_texto_actuacion(n.get("texto", ""))
        etiqueta = ctk.CTkLabel(
            card.body, text=texto_previo, font=fuente(T.meta),
            text_color=C["text_soft"], anchor="w", justify="left",
            wraplength=460,
        )
        etiqueta.grid(row=2, column=0, sticky="ew", pady=(8, 4))
        boton = ctk.CTkButton(
            card.body, text="Ver texto completo", height=32, width=150,
            corner_radius=R.control, fg_color=C["card_hover"],
            hover_color=C["border"], text_color=C["text_soft"],
            font=fuente(T.etiqueta),
        )
        boton.configure(
            command=lambda movimiento=n, accion=boton:
            self._ver_texto_completo(movimiento, accion))
        boton.grid(row=3, column=0, sticky="w", pady=(8, 0))
        card.bind(
            "<Configure>",
            lambda event: etiqueta.configure(
                wraplength=max(event.width - 72, 220)),
            add="+",
        )
        return card

    def _panel_partes(self, master=None):
        card = Tarjeta(master or self.contenido, "Partes intervinientes")
        card.body.grid_columnconfigure(0, weight=1)
        if not self.datos["partes"]:
            ctk.CTkLabel(card.body, text="Sin datos de partes recibidos del SAE.",
                         font=fuente(T.meta), text_color=C["muted"]).grid(row=0, column=0, sticky="w")
        for i, p in enumerate(self.datos["partes"]):
            caja = ctk.CTkFrame(card.body, fg_color=C["card_row"], corner_radius=12)
            caja.grid(row=i, column=0, sticky="ew", pady=(0 if i == 0 else 10, 0))
            caja.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(caja, text=p.get("rol", "Parte").upper(),
                         font=mono(T.etiqueta, "bold"),
                         text_color=C["muted"], anchor="w"
                         ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 2))
            ctk.CTkLabel(caja, text=p.get("nombre", "Nombre no informado"),
                         font=fuente(T.meta, "bold"), text_color=C["text"],
                         anchor="w", wraplength=460, justify="left",
                         ).grid(row=1, column=0, sticky="ew", padx=14)
            detalle = " · ".join(
                str(valor) for valor in (p.get("dni", ""), p.get("detalle", ""))
                if valor
            )
            ctk.CTkLabel(caja, text=detalle, font=mono(T.etiqueta),
                         text_color=C["muted"], anchor="w"
                         ).grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 12))
        return card

    def _panel_juzgado(self, master=None):
        d = self.datos
        card = Tarjeta(
            master or self.contenido, "Juzgado y funcionarios",
            extra=d["centro"].upper())
        card.body.grid_columnconfigure(0, weight=1)
        datos_juzgado = (
            ("OFICINA", d["oficina"]),
            ("JUZGADO", d["juzgado"]),
            ("FUERO", d["fuero"]),
            ("CENTRO JUDICIAL", d["centro"]),
        )
        fila = 0
        for rotulo, valor in datos_juzgado:
            if not valor:
                continue
            ctk.CTkLabel(
                card.body, text=rotulo, font=mono(T.etiqueta, "bold"),
                text_color=C["muted"], anchor="w",
            ).grid(row=fila, column=0, sticky="ew", pady=(0 if fila == 0 else 8, 2))
            fila += 1
            ctk.CTkLabel(
                card.body, text=valor, font=fuente(T.meta, "bold"),
                text_color=C["text_soft"], anchor="w",
                wraplength=460, justify="left",
            ).grid(row=fila, column=0, sticky="ew")
            fila += 1
        ctk.CTkLabel(
            card.body, text="FUNCIONARIOS", font=mono(T.etiqueta, "bold"),
            text_color=C["muted"], anchor="w",
        ).grid(row=fila, column=0, sticky="ew", pady=(12, 2))
        fila += 1
        if not d["funcionarios"]:
            ctk.CTkLabel(
                card.body, text="Sin datos de funcionarios recibidos del SAE.",
                font=fuente(T.etiqueta), text_color=C["dim"], anchor="w",
            ).grid(row=fila, column=0, sticky="w")
        for i, f in enumerate(d["funcionarios"]):
            ctk.CTkLabel(card.body, text=f.get("cargo", "Cargo").upper(),
                         font=mono(T.etiqueta, "bold"),
                         text_color=C["muted"], anchor="w"
                         ).grid(row=fila + i * 2, column=0, sticky="ew",
                                pady=(0 if i == 0 else 12, 2))
            ctk.CTkLabel(card.body, text=f.get("nombre", "Nombre no informado"),
                         font=fuente(T.meta),
                         text_color=C["text_soft"], anchor="w"
                         ).grid(row=fila + i * 2 + 1, column=0, sticky="ew")
        return card

    # --- Pestaña: movimientos ----------------------------------------------
    def _tab_movimientos(self):
        self.contenido.grid_columnconfigure(0, weight=1)
        self.contenido.grid_columnconfigure(1, weight=0)
        card = Tarjeta(self.contenido, "Historial de movimientos", acento="movimientos",
                       extra=f"{len(self.datos['actuaciones'])} ACTUACIONES")
        card.grid(row=0, column=0, columnspan=2, sticky="ew")

        self._labels_mov = []
        if not self.datos["actuaciones"]:
            ctk.CTkLabel(card.body, text="Sin movimientos importados desde el SAE.",
                         font=fuente(T.cuerpo), text_color=C["muted"]).grid(row=0, column=0, sticky="w")
        for i, act in enumerate(self.datos["actuaciones"]):
            caja = ctk.CTkFrame(card.body, fg_color=C["card_row"], corner_radius=12)
            caja.grid(row=i, column=0, sticky="ew", pady=(0 if i == 0 else 10, 0))
            caja.grid_columnconfigure(0, weight=1)

            top = ctk.CTkFrame(caja, fg_color="transparent")
            top.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 2))
            top.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(top, text=act["fecha"], font=mono(T.meta, "bold"),
                         text_color=C["cyan"], anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(top, text=f"Fojas {act.get('fojas') or '?'}", font=mono(T.etiqueta),
                         text_color=C["muted"], anchor="e").grid(row=0, column=2, sticky="e")

            ctk.CTkLabel(caja, text=f"{act['tipo']} · {act['titulo']}",
                         font=fuente(T.item, "bold"), text_color=C["text"], anchor="w"
                         ).grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 0))

            texto_previo = _vista_previa_actuacion(act)
            texto = ctk.CTkLabel(caja, text=texto_previo, font=fuente(T.cuerpo),
                                 text_color=C["text_soft"], anchor="w", justify="left")
            texto.grid(row=2, column=0, sticky="ew", padx=14, pady=(4, 10))
            self._labels_mov.append(texto)

            pie = ctk.CTkFrame(caja, fg_color="transparent")
            pie.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 12))
            boton_texto = ctk.CTkButton(
                pie, text="Ver texto completo", height=30, width=150,
                corner_radius=8, fg_color=C["card_hover"],
                hover_color=C["border"], text_color=C["text_soft"],
                font=fuente(T.etiqueta),
            )
            boton_texto.configure(
                command=lambda movimiento=act, boton=boton_texto:
                self._ver_texto_completo(movimiento, boton))
            boton_texto.grid(row=0, column=0)
            if act.get("pdf"):
                ctk.CTkLabel(pie, text=act["pdf"], font=mono(T.etiqueta),
                             text_color=C["muted"]).grid(row=0, column=1, padx=(10, 0))

        card.bind("<Configure>", self._ajustar_mov, add="+")

    def _ajustar_mov(self, event):
        for lbl in getattr(self, "_labels_mov", []):
            lbl.configure(wraplength=max(event.width - 80, 260))

    # --- Pestaña: documentos ------------------------------------------------
    def _tab_documentos(self):
        self.contenido.grid_columnconfigure(0, weight=1)
        card = Tarjeta(self.contenido, "Documentos descargados",
                       extra=f"{len(self.datos['pdfs'])} ARCHIVOS")
        card.grid(row=0, column=0, sticky="ew")

        for i, doc in enumerate(self.datos["pdfs"]):
            fila = ctk.CTkFrame(card.body, fg_color=C["card_row"], corner_radius=10)
            fila.grid(row=i, column=0, sticky="ew", pady=(0 if i == 0 else 8, 0))
            fila.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(fila, text=doc["nombre"], font=mono(T.meta),
                         text_color=C["text_soft"], anchor="w"
                         ).grid(row=0, column=0, sticky="ew", padx=14, pady=12)
            ctk.CTkLabel(fila, text=f"{doc['peso']} · {doc['fecha']}", font=mono(T.etiqueta),
                         text_color=C["muted"]).grid(row=0, column=1, padx=(0, 14))
            ctk.CTkButton(fila, text="Abrir", height=30, width=80, corner_radius=8,
                          fg_color=C["card_hover"], hover_color=C["border"],
                          text_color=C["text_soft"], font=fuente(T.etiqueta)
                          ).grid(row=0, column=2, padx=(0, 12))

        texto_documentos = ("El SAE no proporciono documentos descargados."
                            if not self.datos["pdfs"] else
                            "Documentos recibidos desde el SAE.")
        ctk.CTkLabel(card.body, text=texto_documentos,
                     font=fuente(T.meta), text_color=C["muted"], anchor="w"
                     ).grid(row=len(self.datos["pdfs"]), column=0, sticky="ew", pady=(12, 0))

    # --- Pestaña: agenda del caso -------------------------------------------
    def _tab_agenda(self):
        self.contenido.grid_columnconfigure(0, weight=1)
        card = Tarjeta(self.contenido, "Agenda del caso", acento="agenda")
        card.grid(row=0, column=0, sticky="ew")

        if not self.datos["agenda"]:
            ctk.CTkLabel(card.body, text="No hay vencimientos informados para este expediente.",
                         font=fuente(T.cuerpo), text_color=C["muted"]).grid(row=0, column=0, sticky="w")
        for i, ev in enumerate(self.datos["agenda"]):
            fila = ctk.CTkFrame(card.body, fg_color=C["card_row"], corner_radius=10)
            fila.grid(row=i, column=0, sticky="ew", pady=(0 if i == 0 else 8, 0))
            fila.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(fila, text=ev["fecha"], font=mono(T.meta, "bold"),
                         text_color=C["cyan"]).grid(row=0, column=0, padx=14, pady=12)
            ctk.CTkLabel(fila, text=ev["titulo"], font=fuente(T.cuerpo),
                         text_color=C["text_soft"], anchor="w"
                         ).grid(row=0, column=1, sticky="ew")
            _chip(fila, ev["tipo"].upper()).grid(row=0, column=2, padx=(0, 14))

    # --- Acciones -----------------------------------------------------------
    def _volver(self):
        if self.on_back:
            self.on_back()

    def _ver_original(self):
        if self.on_ver_original:
            self.on_ver_original(self.datos)

    def _ver_texto_completo(self, actuacion, boton):
        if actuacion.get("texto_completo"):
            self._abrir_ventana_texto(actuacion)
            return
        if self.on_load_actuacion:
            boton.configure(state="disabled", text="Consultando SAE...")
            self.estado_actualizacion.configure(
                text="Buscando solo esta actuación en el SAE...",
                text_color=C["muted"],
            )
            self.on_load_actuacion(
                self.datos["expediente"],
                actuacion,
                lambda actualizada, error: self._finalizar_texto_actuacion(
                    actuacion, boton, actualizada, error),
            )
            return
        if self.on_ver_original:
            self.on_ver_original(self.datos)
            return
        self._abrir_ventana_texto(actuacion)

    def _finalizar_texto_actuacion(
            self, actuacion, boton, actualizada, error):
        boton.configure(state="normal", text="Ver texto completo")
        if error:
            self.estado_actualizacion.configure(
                text=f"No se pudo consultar la actuación: {error}",
                text_color=C["error"],
            )
            return
        actuacion.update(actualizada)
        self.estado_actualizacion.configure(
            text="Texto completo descargado desde el SAE.",
            text_color=C["ok"],
        )
        self._abrir_ventana_texto(actuacion)

    def _abrir_ventana_texto(self, actuacion):
        if self.lector_texto is not None:
            self.lector_texto.destroy()

        lector = ctk.CTkFrame(
            self, fg_color=C["bg"], corner_radius=0,
            border_width=1, border_color=C["border"],
        )
        lector.place(relx=0, rely=0, relwidth=1, relheight=1)
        lector.grid_columnconfigure(0, weight=1)
        lector.grid_rowconfigure(1, weight=1)
        self.lector_texto = lector
        self._lector_nivel_fuente = 0

        cabecera = ctk.CTkFrame(lector, fg_color=C["card"], corner_radius=12)
        cabecera.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 12))
        cabecera.grid_columnconfigure(0, weight=1)
        self._lector_fuentes = []
        titulo_lector = ctk.CTkLabel(
            cabecera,
            text=f"{actuacion.get('tipo', 'Actuación')} · {actuacion.get('titulo', '')}",
            font=fuente(20, "bold"), text_color=C["text"], anchor="w",
            wraplength=900, justify="left",
        )
        titulo_lector.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 2))
        self._lector_fuentes.append((titulo_lector, 20, "bold"))
        ctk.CTkLabel(
            cabecera,
            text=f"Exp. {self.datos['expediente']}  ·  {actuacion.get('fecha', '')}",
            font=mono(14), text_color=C["cyan"], anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))

        controles_fuente = ctk.CTkFrame(cabecera, fg_color="transparent")
        controles_fuente.grid(row=0, column=1, rowspan=2, sticky="e", padx=16)
        estilo_boton_zoom = {
            "height": 34,
            "width": 40,
            "corner_radius": 8,
            "fg_color": C["card_hover"],
            "hover_color": C["border"],
            "text_color": C["text"],
            "font": fuente(18, "bold"),
        }
        ctk.CTkButton(
            controles_fuente, text="−", command=lambda: self._ajustar_fuente_lector(-1),
            **estilo_boton_zoom,
        ).grid(row=0, column=0, padx=3)
        self._lector_zoom_reset = ctk.CTkButton(
            controles_fuente, text="🔍 100%",
            command=lambda: self._ajustar_fuente_lector(0, restablecer=True),
            width=86, height=34, corner_radius=8,
            fg_color=C["card_hover"], hover_color=C["border"],
            text_color=C["cyan"], font=fuente(T.meta, "bold"),
        )
        self._lector_zoom_reset.grid(row=0, column=1, padx=3)
        ctk.CTkButton(
            controles_fuente, text="+", command=lambda: self._ajustar_fuente_lector(1),
            **estilo_boton_zoom,
        ).grid(row=0, column=2, padx=3)

        scroll = ctk.CTkScrollableFrame(
            lector, fg_color=C["card"], corner_radius=12,
            scrollbar_button_color=C["card_hover"],
            scrollbar_button_hover_color=C["accent"],
        )
        scroll.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 12))
        scroll.grid_columnconfigure(0, weight=1)
        self._lector_scroll = scroll

        contenido = _formatear_texto_actuacion(actuacion.get("texto", ""))
        if contenido:
            secciones = contenido.split("\n\n")
            primera_linea = True
            for indice, seccion in enumerate(secciones):
                if not seccion:
                    continue
                tipo = _clasificar_linea_actuacion(
                    seccion, primera_linea=primera_linea)
                primera_linea = False
                estilos = {
                    "titulo": (20, "bold", C["cyan"]),
                    "subtitulo": (18, "bold", C["violet"]),
                    "parrafo": (17, "normal", C["text_soft"]),
                    "final": (16, "bold", C["gold"]),
                }
                font_size, font_weight, color = estilos[tipo]
                etiqueta = ctk.CTkLabel(
                    scroll, text=seccion,
                    font=fuente(font_size, font_weight), text_color=color,
                    anchor="w", justify="left", wraplength=900,
                )
                etiqueta.grid(
                    row=indice, column=0, sticky="ew", padx=18,
                    pady=(14 if indice == 0 or tipo in ("titulo", "subtitulo") else 7, 4),
                )
                self._lector_fuentes.append(
                    (etiqueta, font_size, font_weight))
        else:
            etiqueta_vacia = ctk.CTkLabel(
                scroll, text="El SAE no devolvió texto para esta actuación.",
                font=fuente(17), text_color=C["muted"], anchor="w",
            )
            etiqueta_vacia.grid(row=0, column=0, sticky="ew", padx=18, pady=18)
            self._lector_fuentes.append((etiqueta_vacia, 17, "normal"))

        scroll.bind("<Configure>", self._ajustar_ancho_lector, add="+")

        pie = ctk.CTkFrame(lector, fg_color="transparent")
        pie.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 18))
        pie.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            pie, text="Ver expediente", height=38, width=150,
            corner_radius=R.control, fg_color=C["accent"],
            hover_color=C["accent_hover"], font=fuente(T.meta, "bold"),
            command=self._ver_expediente_desde_lector,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            pie, text="Volver al detalle", height=38, width=150,
            corner_radius=R.control, fg_color=C["card_hover"],
            hover_color=C["border"], text_color=C["text_soft"],
            font=fuente(T.meta), command=self._cerrar_lector_texto,
        ).grid(row=0, column=1, sticky="e")
        lector.bind("<Configure>", self._ajustar_ancho_lector, add="+")

    def _ajustar_ancho_lector(self, event):
        ancho = max(event.width - 88, 220)
        for fuente_lector in getattr(self, "_lector_fuentes", []):
            etiqueta = fuente_lector[0]
            etiqueta.configure(wraplength=ancho)

    def _ajustar_fuente_lector(self, cambio, restablecer=False):
        if restablecer:
            self._lector_nivel_fuente = 0
        else:
            self._lector_nivel_fuente = max(
                -2, min(6, self._lector_nivel_fuente + cambio))
        factor = 100 + self._lector_nivel_fuente * 10
        self._lector_zoom_reset.configure(text=f"🔍 {factor}%")
        for etiqueta, tamano_base, peso in self._lector_fuentes:
            etiqueta.configure(
                font=fuente(
                    tamano_base + self._lector_nivel_fuente * 2, peso))

    def _cerrar_lector_texto(self):
        if self.lector_texto is not None:
            self.lector_texto.destroy()
            self.lector_texto = None

    def _ver_expediente_desde_lector(self):
        self._cerrar_lector_texto()
        if self.on_open_expediente:
            self.on_open_expediente(self.datos)

    def _actualizar(self):
        if not self.on_sync:
            self.estado_actualizacion.configure(
                text="No hay una acción de sincronización configurada.",
                text_color=C["error"],
            )
            return
        self.btn_actualizar.configure(state="disabled", text="Consultando el SAE...")
        self.estado_actualizacion.configure(text="Sincronizando este expediente...")
        self.on_sync(self.datos["expediente"], self._finalizar_actualizacion)

    def _finalizar_actualizacion(self, _resultado=None, error=None):
        self.btn_actualizar.configure(
            state="normal", text="Actualizar desde el SAE")
        self.estado_actualizacion.configure(
            text=f"No se pudo actualizar: {error}" if error
            else "Actualización completada.",
            text_color=C["error"] if error else C["ok"],
        )
