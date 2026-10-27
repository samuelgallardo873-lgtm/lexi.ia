"""
LexBot - Vista Expedientes: grilla de tarjetas y buscador.

Antes era una tabla. Con carátulas largas y más de cien causas, la tabla
obliga a leer en línea recta y recorta el texto; las tarjetas dejan respirar
cada causa y permiten mostrar carátula completa, juzgado y estado sin apretar.

La cantidad de columnas se recalcula según el ancho disponible.
"""

import re
import sqlite3
from datetime import datetime

import customtkinter as ctk

from theme import C, ESTADO_CAUSA, R, S, T, fuente, mono

ESTADOS = ["Activo", "En trámite", "Paralizado", "Archivado"]
CENTROS_JUDICIALES = ["Capital", "Concepción", "Monteros", "Este", "Paz"]
FUEROS = [
    "Familia y Sucesiones",
    "Civil y Comercial Común",
    "Contencioso Administrativo",
    "Trabajo",
    "Penal",
    "Documentos y Locaciones",
    "Cobros y Apremios",
    "Otros",
]

ANCHO_MINIMO_TARJETA = 380      # por debajo de esto el texto empieza a apretarse


def _fecha_ultima_amigable(valor):
    valor = str(valor or "").strip()
    if not valor or valor == "—":
        return "Fecha no informada"

    fecha = None
    try:
        fecha = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        for formato in (
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
                "%d/%m/%Y", "%Y-%m-%d"):
            try:
                fecha = datetime.strptime(valor, formato)
                break
            except ValueError:
                continue
    if fecha is None:
        return valor

    ahora = datetime.now(fecha.tzinfo) if fecha.tzinfo else datetime.now()
    diferencia = ahora - fecha
    segundos = diferencia.total_seconds()
    if 0 <= segundos < 60:
        return "Últ. mov. hace menos de 1 min"
    if 60 <= segundos < 3600:
        minutos = int(segundos // 60)
        return f"Últ. mov. hace {minutos} min"
    if 3600 <= segundos < 86400:
        horas = int(segundos // 3600)
        return f"Últ. mov. hace {horas} h"
    if 86400 <= segundos < 172800:
        return f"Últ. mov. ayer, {fecha:%H:%M}"

    meses = (
        "ene", "feb", "mar", "abr", "may", "jun",
        "jul", "ago", "sep", "oct", "nov", "dic",
    )
    anio = f" de {fecha.year}" if fecha.year != ahora.year else ""
    return (
        f"Últ. mov. {fecha.day} de {meses[fecha.month - 1]}{anio}, "
        f"{fecha:%H:%M}"
    )


class TarjetaExpediente(ctk.CTkFrame):
    """Una causa: número, estado, carátula, juzgado y última novedad."""

    def __init__(self, master, item, on_open=None, on_monitor_change=None, corte=360):
        super().__init__(master, fg_color="#0D1728", corner_radius=16,
                         border_width=1, border_color="#24354D", cursor="hand2")
        self.item = item
        self.on_open = on_open
        self.on_monitor_change = on_monitor_change
        self._pulso_activo = False
        self._id_pulso = None
        self.grid_columnconfigure(0, weight=1)

        color_estado = ESTADO_CAUSA.get(item.get("estado"), C["muted"])
        es_activo = item.get("estado") == "Activo"

        ctk.CTkFrame(
            self, height=2, width=1,
            fg_color="#39D98A" if es_activo else color_estado,
            corner_radius=1,
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(13, 0))

        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.grid(row=1, column=0, sticky="nsew", padx=18, pady=(12, 17))
        cuerpo.grid_columnconfigure(0, weight=1)

        # Encabezado con identificador y estado.
        top = ctk.CTkFrame(cuerpo, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            top, text=f"EXP. {item['expediente']}",
            font=fuente(T.item, "bold"), text_color="#45E0EF", anchor="w",
        ).grid(row=0, column=0, sticky="w")

        estado = ctk.CTkFrame(
            top, fg_color="#0D302A" if es_activo else C["card_row"],
            corner_radius=12, border_width=1,
            border_color="#1C5947" if es_activo else C["border"],
        )
        estado.grid(row=0, column=1, sticky="e", padx=(8, 0))
        indicador = ctk.CTkFrame(
            estado, width=12, height=12, corner_radius=6,
            fg_color="#14543F" if es_activo else C["border"],
        )
        indicador.grid(row=0, column=0, padx=(9, 5), pady=6)
        ctk.CTkFrame(
            indicador, width=6, height=6, corner_radius=3,
            fg_color="#4DFFA5" if es_activo else color_estado,
        ).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(
            estado, text=item.get("estado", "Sin estado").upper(),
            font=mono(T.etiqueta, "bold"),
            text_color="#66F0A8" if es_activo else color_estado,
        ).grid(row=0, column=1, padx=(0, 10), pady=5)

        monitoreo_activo = bool(item.get("monitorear", 1))
        self.var_monitorear = ctk.BooleanVar(value=monitoreo_activo)
        self.switch_monitorear = ctk.CTkSwitch(
            top, text="Monitoreo Activo" if monitoreo_activo else "Pausado",
            variable=self.var_monitorear,
            width=122, height=20, switch_width=32, switch_height=17,
            font=fuente(T.etiqueta), text_color=C["muted"],
            fg_color=C["border"], progress_color=C["accent"],
            button_color=C["text_soft"], button_hover_color=C["text"],
            command=self._cambiar_monitoreo)
        self.switch_monitorear.grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self.caratula = ctk.CTkLabel(
            cuerpo, text=item.get("caratula", ""),
            font=fuente(T.item, "bold"), text_color=C["text"],
            anchor="w", justify="left", wraplength=corte,
        )
        self.caratula.grid(row=2, column=0, sticky="ew", pady=(13, 0))

        jurisdiccion = "  ·  ".join(
            value for value in (
                item.get("centro_judicial", ""),
                item.get("fuero", ""),
            ) if value
        )
        self.juzgado = ctk.CTkLabel(
            cuerpo, text=f"⚖  {jurisdiccion}" if jurisdiccion else "",
            font=fuente(T.etiqueta), text_color=C["muted"],
            anchor="w", justify="left", wraplength=corte,
        )
        self.juzgado.grid(row=3, column=0, sticky="ew", pady=(7, 0))

        oficina = str(item.get("oficina") or item.get("juzgado") or "").strip()
        self.oficina = ctk.CTkLabel(
            cuerpo,
            text=f"🏛  {oficina}" if oficina else "Oficina judicial no informada",
            font=fuente(T.meta, "bold" if oficina else "normal"),
            text_color=C["violet"] if oficina else C["dim"],
            anchor="w", justify="left", wraplength=corte,
        )
        self.oficina.grid(row=4, column=0, sticky="ew", pady=(6, 0))

        actividad = ctk.CTkFrame(
            cuerpo, fg_color="#0A1220", corner_radius=11,
            border_width=1, border_color="#1B2A3E",
        )
        actividad.grid(row=5, column=0, sticky="ew", pady=(13, 0))
        actividad.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            actividad, text="ÚLTIMA ACTUACIÓN",
            font=mono(T.etiqueta, "bold"), text_color=C["muted"], anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=13, pady=(11, 3))
        self.novedad = ctk.CTkLabel(
            actividad, text=item.get("novedad", ""),
            font=fuente(T.meta), text_color=C["text_soft"],
            anchor="w", justify="left", wraplength=corte - 32,
        )
        self.novedad.grid(row=1, column=0, sticky="ew", padx=13, pady=(0, 5))
        ctk.CTkLabel(
            actividad, text=f"📅  {_fecha_ultima_amigable(item.get('ultimo'))}",
            font=fuente(T.etiqueta), text_color=C["dim"], anchor="w",
        ).grid(row=2, column=0, sticky="ew", padx=13, pady=(0, 11))

        pie = ctk.CTkFrame(cuerpo, fg_color="transparent")
        pie.grid(row=6, column=0, sticky="ew", pady=(13, 0))
        pie.grid_columnconfigure(0, weight=1)
        self.boton_abrir = ctk.CTkButton(
            pie, text="Abrir", width=100, height=34, corner_radius=18,
            fg_color="#1769D2", hover_color="#0EA5C8",
            text_color="#F2FAFF", font=fuente(T.meta, "bold"),
            command=self._abrir,
        )
        self.boton_abrir.grid(row=0, column=1, sticky="e")
        self.boton_abrir.bind(
            "<Enter>", lambda _event: self.boton_abrir.configure(text="Abrir  →"))
        self.boton_abrir.bind(
            "<Leave>", lambda _event: self.boton_abrir.configure(text="Abrir"))

        for w in (self, cuerpo, top, self.caratula, self.juzgado, self.oficina,
                  self.novedad, actividad):
            w.bind("<Button-1>", lambda _e: self._abrir())

        if es_activo:
            self.bind("<Destroy>", self._cancelar_pulso, add="+")
            self._animar_indicador(indicador)

    def _abrir(self):
        if self.on_open:
            self.on_open(self.item)

    def _animar_indicador(self, indicador):
        if not indicador.winfo_exists():
            return
        self._pulso_activo = not self._pulso_activo
        indicador.configure(
            fg_color="#176747" if self._pulso_activo else "#103F32")
        self._id_pulso = self.after(
            1100, lambda: self._animar_indicador(indicador))

    def _cancelar_pulso(self, event):
        if event.widget == self and self._id_pulso is not None:
            self.after_cancel(self._id_pulso)
            self._id_pulso = None

    def _cambiar_monitoreo(self):
        if self.on_monitor_change:
            self.on_monitor_change(self.item, self.var_monitorear.get(), self.var_monitorear)
        self.switch_monitorear.configure(
            text="Monitoreo Activo" if self.var_monitorear.get() else "Pausado")


class ExpedientesView(ctk.CTkFrame):
    def __init__(self, master, expedientes=None, on_open=None,
                 on_monitor_change=None, on_sync=None, on_create=None, **kwargs):
        super().__init__(master, fg_color=C["bg"], corner_radius=0, **kwargs)
        self.datos = list(expedientes or [])
        self.on_open = on_open
        self.on_monitor_change = on_monitor_change
        self.on_sync = on_sync
        self.on_create = on_create
        self.columnas = 2
        self._ancho_util = 1040
        self._pendiente = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_filtros()

        self.grilla = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.grilla.grid(row=2, column=0, sticky="nsew", padx=S.xl, pady=(0, S.xl))

        self.estado_accion = ctk.CTkLabel(
            self, text="", font=fuente(T.meta), text_color=C["muted"], anchor="w")
        self.estado_accion.grid(row=3, column=0, sticky="ew", padx=S.xl,
                                pady=(0, S.sm))
        self._render()
        # El evento se escucha en la vista, no en la grilla: dentro del
        # callback de la grilla no se pueden destruir sus propios hijos.
        self.bind("<Configure>", self._quizas_recolumnar, add="+")

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=S.xl, pady=(S.xl, S.md))
        header.grid_columnconfigure(0, weight=1)

        titulo = ctk.CTkFrame(header, fg_color="transparent")
        titulo.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(titulo, text="Expedientes", font=fuente(T.titulo_pagina, "bold"),
                     text_color=C["text"], anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(titulo, text="Causas en seguimiento automático desde el SAE",
                     font=fuente(T.meta), text_color=C["muted"], anchor="w"
                     ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        acciones = ctk.CTkFrame(header, fg_color="transparent")
        acciones.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            acciones, text="+ Nuevo Expediente", height=42, width=170,
            corner_radius=R.control, fg_color=C["accent"], hover_color=C["accent_hover"],
            text_color=C["text"], font=fuente(T.meta, "bold"),
            command=self._nuevo_expediente).grid(row=0, column=0, padx=(0, S.sm))
        ctk.CTkButton(
            acciones, text="Importar del SAE", height=42, width=145,
            corner_radius=R.control, fg_color=C["card"], hover_color=C["card_hover"],
            text_color=C["text"], font=fuente(T.meta, "bold"),
            command=self._sincronizar).grid(row=0, column=1)

    def _nuevo_expediente(self):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Nuevo expediente")
        dialogo.geometry("500x570")
        dialogo.resizable(False, False)
        dialogo.transient(self.winfo_toplevel())
        dialogo.grab_set()

        contenido = ctk.CTkFrame(dialogo, fg_color=C["bg"], corner_radius=0)
        contenido.pack(fill="both", expand=True, padx=24, pady=24)
        contenido.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            contenido, text="Nuevo Expediente", font=fuente(T.titulo_pagina, "bold"),
            text_color=C["text"], anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 18))

        ctk.CTkLabel(
            contenido, text="CENTRO JUDICIAL", font=mono(T.etiqueta, "bold"),
            text_color=C["muted"], anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(0, 4))
        centro = ctk.StringVar(value=CENTROS_JUDICIALES[0])
        ctk.CTkOptionMenu(
            contenido, values=CENTROS_JUDICIALES, variable=centro, height=40,
            fg_color=C["field"], button_color=C["field"],
            button_hover_color=C["card_hover"], text_color=C["text"],
            dropdown_fg_color=C["card"], dropdown_text_color=C["text"],
            font=fuente(T.cuerpo),
        ).grid(row=2, column=0, sticky="ew", pady=(0, 14))

        ctk.CTkLabel(
            contenido, text="FUERO", font=mono(T.etiqueta, "bold"),
            text_color=C["muted"], anchor="w",
        ).grid(row=3, column=0, sticky="ew", pady=(0, 4))
        fuero = ctk.StringVar(value=FUEROS[0])
        ctk.CTkOptionMenu(
            contenido, values=FUEROS, variable=fuero, height=40,
            fg_color=C["field"], button_color=C["field"],
            button_hover_color=C["card_hover"], text_color=C["text"],
            dropdown_fg_color=C["card"], dropdown_text_color=C["text"],
            font=fuente(T.cuerpo),
        ).grid(row=4, column=0, sticky="ew", pady=(0, 14))

        ctk.CTkLabel(
            contenido, text="NÚMERO DE EXPEDIENTE / AÑO",
            font=mono(T.etiqueta, "bold"), text_color=C["muted"], anchor="w",
        ).grid(row=5, column=0, sticky="ew", pady=(0, 4))
        numero = ctk.CTkEntry(
            contenido, height=40, fg_color=C["field"], border_width=0,
            text_color=C["text"], placeholder_text="12392/21",
            font=mono(T.cuerpo),
        )
        numero.grid(row=6, column=0, sticky="ew", pady=(0, 14))

        ctk.CTkLabel(
            contenido, text="CARÁTULA (OPCIONAL)", font=mono(T.etiqueta, "bold"),
            text_color=C["muted"], anchor="w",
        ).grid(row=7, column=0, sticky="ew", pady=(0, 4))
        caratula = ctk.CTkEntry(
            contenido, height=40, fg_color=C["field"], border_width=0,
            text_color=C["text"], placeholder_text="García c/ Sucesión",
            font=fuente(T.cuerpo),
        )
        caratula.grid(row=8, column=0, sticky="ew", pady=(0, 12))
        error = ctk.CTkLabel(
            contenido, text="", font=fuente(T.meta), text_color=C["error"],
            anchor="w", wraplength=420,
        )
        error.grid(row=9, column=0, sticky="ew", pady=(0, 12))

        def guardar():
            valor_numero = numero.get().strip()
            if not re.fullmatch(r"\d{1,8}\s*/\s*\d{2,4}", valor_numero):
                error.configure(text="Ingresa un número válido en formato expediente/año, por ejemplo 12392/21.")
                return
            if not self.on_create:
                error.configure(text="No está configurado el guardado local del expediente.")
                return
            expediente = {
                "expediente": re.sub(r"\s+", "", valor_numero),
                "caratula": caratula.get().strip(),
                "fuero": fuero.get(),
                "centro_judicial": centro.get(),
            }
            try:
                creado = self.on_create(expediente)
                if creado is not None:
                    if isinstance(creado, dict):
                        self.datos.append(creado)
                    else:
                        self.datos = list(creado)
                self._render()
            except (sqlite3.Error, ValueError, OSError) as exc:
                error.configure(text=f"No se pudo guardar el expediente: {exc}")
                return
            self.estado_accion.configure(
                text="Expediente agregado localmente. La sincronización del SAE confirmará sus datos.",
                text_color=C["ok"],
            )
            dialogo.destroy()

        ctk.CTkButton(
            contenido, text="Guardar expediente", height=42,
            corner_radius=R.control, fg_color=C["accent"],
            hover_color=C["accent_hover"], font=fuente(T.cuerpo, "bold"),
            command=guardar,
        ).grid(row=10, column=0, sticky="ew", pady=(4, 0))

    def _build_filtros(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=1, column=0, sticky="ew", padx=S.xl, pady=(0, S.md))
        barra.grid_columnconfigure(0, weight=1)

        self.buscador = ctk.CTkEntry(
            barra, height=44, corner_radius=R.control, border_width=0, fg_color=C["field"],
            text_color=C["text"], font=fuente(T.cuerpo),
            placeholder_text="Buscar por número, carátula, fuero o juzgado...")
        self.buscador.grid(row=0, column=0, sticky="ew", padx=(0, S.md))
        self.buscador.bind("<KeyRelease>", lambda _e: self._render())

        self.var_estado = ctk.StringVar(value="Todos")
        ctk.CTkOptionMenu(
            barra, values=["Todos"] + ESTADOS, variable=self.var_estado, height=44,
            width=170, corner_radius=R.control, fg_color=C["field"],
            button_color=C["field"], button_hover_color=C["card_hover"],
            text_color=C["text"], dropdown_fg_color=C["card"],
            dropdown_text_color=C["text"], dropdown_hover_color=C["card_hover"],
            font=fuente(T.cuerpo), command=lambda _v: self._render()
            ).grid(row=0, column=1, padx=(0, S.md))

        self.contador = ctk.CTkLabel(barra, text="", font=mono(T.meta),
                                     text_color=C["muted"])
        self.contador.grid(row=0, column=2)

    # --- Datos --------------------------------------------------------------
    def _visibles(self):
        texto = self.buscador.get().strip().lower()
        estado = self.var_estado.get()
        filas = self.datos
        if estado != "Todos":
            filas = [f for f in filas if f.get("estado") == estado]
        if texto:
            filas = [f for f in filas
                     if texto in " ".join(str(v) for v in f.values()).lower()]
        return filas

    def _quizas_recolumnar(self, event):
        """
        Recalcula columnas y ancho de corte cuando cambia el tamaño.

        El redibujado se posterga con un temporizador en lugar de hacerse
        dentro del callback: destruir las tarjetas mientras Tk procesa el
        redimensionado rompe el recorrido de widgets. Si llegan varios eventos
        seguidos, solo sobrevive el último.
        """
        disponible = max(event.width - (S.xl * 2) - 24, 200)
        nuevas = max(1, min(3, disponible // ANCHO_MINIMO_TARJETA))
        # El umbral de 60 px evita redibujar por la barra de desplazamiento,
        # que son unos 16 px y haría oscilar el ancho.
        if nuevas == self.columnas and abs(disponible - self._ancho_util) <= 60:
            return

        self.columnas = nuevas
        self._ancho_util = disponible
        if self._pendiente is not None:
            self.after_cancel(self._pendiente)
        self._pendiente = self.after(60, self._redibujar)

    def _redibujar(self):
        self._pendiente = None
        self._render()

    def _render(self):
        for w in self.grilla.winfo_children():
            w.destroy()

        filas = self._visibles()
        self.contador.configure(text=f"{len(filas)} de {len(self.datos)} causas")

        # El grupo "uniform" solo debe incluir las columnas en uso: si queda
        # dentro una columna vacía, Tk reparte el ancho entre las tres y las
        # tarjetas salen más angostas de lo que corresponde.
        for col in range(3):
            if col < self.columnas:
                self.grilla.grid_columnconfigure(col, weight=1, uniform="tarjetas")
            else:
                self.grilla.grid_columnconfigure(col, weight=0, uniform="")

        if not filas:
            mensaje = (
                "Sin expedientes registrados. Realiza una sincronizacion con el SAE."
                if not self.datos else
                "No hay expedientes que coincidan con esta busqueda o filtro."
            )
            ctk.CTkLabel(self.grilla, text=mensaje,
                         font=fuente(T.cuerpo), text_color=C["muted"]
                         ).grid(row=0, column=0, columnspan=self.columnas, pady=50)
            return

        ancho_grilla = self.grilla.winfo_width()
        if ancho_grilla < 200:                 # todavía no se dibujó
            ancho_grilla = self._ancho_util
        corte = max(ancho_grilla // self.columnas - 110, 180)
        for i, item in enumerate(filas):
            fila, col = divmod(i, self.columnas)
            TarjetaExpediente(
                self.grilla, item, on_open=self._abrir,
                on_monitor_change=self._cambiar_monitoreo, corte=corte).grid(
                row=fila, column=col, sticky="nsew",
                padx=(0 if col == 0 else S.md, 0), pady=(0 if fila == 0 else S.md, 0))


    # --- Acciones -----------------------------------------------------------
    def actualizar_expedientes(self, expedientes):
        self.datos = list(expedientes)
        self._render()

    def _cambiar_monitoreo(self, item, monitorear, variable):
        try:
            if self.on_monitor_change:
                self.on_monitor_change(item["expediente"], monitorear)
            item["monitorear"] = int(monitorear)
            self.estado_accion.configure(
                text="Seguimiento actualizado.",
                text_color=C["ok"],
            )
        except (sqlite3.Error, LookupError, OSError) as exc:
            variable.set(not monitorear)
            self.estado_accion.configure(
                text=f"No se pudo actualizar el seguimiento: {exc}",
                text_color=C["error"],
            )

    def _sincronizar(self):
        if self.on_sync:
            self.estado_accion.configure(
                text="Importando expedientes del SAE...",
                text_color=C["muted"],
            )
            self.on_sync(self._sincronizacion_terminada)

    def _sincronizacion_terminada(self, expedientes=None, error=None):
        if error:
            self.estado_accion.configure(
                text=f"No se pudieron importar los expedientes: {error}",
                text_color=C["error"],
            )
            return
        self.datos = list(expedientes or [])
        self.estado_accion.configure(
            text=f"Lista del SAE actualizada: {len(self.datos)} expedientes.",
            text_color=C["ok"],
        )
        self._render()

    def _abrir(self, item):
        if self.on_open:
            self.on_open(item)
