"""
LexBot - Punto de entrada.

Requisitos:
    pip install customtkinter
    pip install playwright
    playwright install chromium
    pip install pillow        (opcional: solo para mostrar la foto del abogado)
Ejecutar:
    python main.py

Archivos del proyecto (todos en la misma carpeta):
    theme.py                    paleta, tipografía y escala
    ajustes.py                  preferencias guardadas en disco
    database.py                 expedientes y actuaciones en SQLite
    ai_service.py               consultas locales y fundamentadas de LEXI
    credential_store.py         credenciales en Windows Credential Manager
    sae_connector.py            inicio de sesión y lectura del portal SAE
    bot_scraper.py               sincronización de expedientes y barrido
    widgets.py                  logo, avatar y piezas reutilizables
    main.py                     ventana principal y navegación
    view_dashboard.py           DashboardView
    view_expedientes.py         ExpedientesView
    view_expediente_detalle.py  ExpedienteDetalleView
    view_alertas.py             AlertasView
    view_calendario.py          CalendarioView
    view_configuracion.py       ConfiguracionView
    view_lexi.py                LexiView
"""

from datetime import datetime
import sqlite3
import threading

import customtkinter as ctk

import ajustes
import database
from ai_service import OllamaService
from bot_scraper import (
    ejecutar_barrido_diario,
    sincronizar_actuacion,
    sincronizar_expediente,
    sincronizar_expedientes,
)
from credential_store import leer_credenciales
from sae_connector import probar_conexion
from theme import C, R, S, T, aplicar_escala, fuente, mono
from view_alertas import AlertasView
from view_calendario import CalendarioView
from view_configuracion import ConfiguracionView
from view_dashboard import DashboardView
from view_expediente_detalle import ExpedienteDetalleView
from view_expedientes import ExpedientesView
from view_lexi import LexiView
from widgets import Avatar, LogoBalanza, punto

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

NAV_PRINCIPAL = [
    ("Dashboard", "Panel de control"),
    ("LEXI", "Asistente de expedientes"),
    ("Expedientes", "Causas en seguimiento"),
    ("Alertas / Inactividad", "Plazos y caducidad"),
    ("Calendario de Vencimientos", "Agenda judicial"),
]
NAV_PIE = ("Configuración", "Preferencias y cuenta")


class Sidebar(ctk.CTkFrame):
    """Barra lateral: marca, navegación y ficha del profesional."""

    def __init__(self, master, on_navigate, on_toggle):
        super().__init__(master, width=250, corner_radius=0, fg_color=C["sidebar"])
        self.on_navigate = on_navigate
        self.on_toggle = on_toggle
        self.buttons = {}
        self.colapsada = False
        self.items_navegacion = []

        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(len(NAV_PRINCIPAL) + 2, weight=1)

        self._build_marca()

        self.etiqueta_navegacion = ctk.CTkLabel(
            self, text="NAVEGACIÓN", font=mono(T.etiqueta),
            text_color=C["dim"], anchor="w")
        self.etiqueta_navegacion.grid(
            row=1, column=0, padx=S.xl, pady=(S.lg, S.sm), sticky="w")
        self.items_navegacion.append(self.etiqueta_navegacion)

        for i, (nombre, _) in enumerate(NAV_PRINCIPAL, start=2):
            self.buttons[nombre] = self._nav_button(nombre, row=i)
            self.items_navegacion.append(self.buttons[nombre])

        self.buttons[NAV_PIE[0]] = self._nav_button(
            NAV_PIE[0], row=len(NAV_PRINCIPAL) + 3, pady=(S.xs, S.md))
        self.items_navegacion.append(self.buttons[NAV_PIE[0]])

        self._build_perfil(row=len(NAV_PRINCIPAL) + 4)

    def _build_marca(self):
        self.marca = ctk.CTkFrame(self, fg_color="transparent")
        self.marca.grid(row=0, column=0, padx=S.xl, pady=(S.xl + 4, 2), sticky="ew")
        self.marca.grid_columnconfigure(1, weight=1)

        self.logo = LogoBalanza(self.marca, lado=34)
        self.logo.grid(row=0, column=0, rowspan=2, padx=(0, S.md))
        self.logo.configure(cursor="hand2")
        self.logo.bind("<Button-1>", self._al_clic_logo)
        self.nombre_marca = ctk.CTkLabel(
            self.marca, text="LexBot SAE", font=fuente(T.titulo_app, "bold"),
            text_color=C["text"], anchor="w")
        self.nombre_marca.grid(row=0, column=1, sticky="w")
        self.subtitulo_marca = ctk.CTkLabel(
            self.marca, text="GESTIÓN JUDICIAL", font=mono(9),
            text_color=C["gold"], anchor="w")
        self.subtitulo_marca.grid(row=1, column=1, sticky="w", pady=(1, 0))
        self.btn_ocultar = ctk.CTkButton(
            self.marca, text="‹", width=30, height=30, corner_radius=8,
            fg_color="transparent", hover_color=C["card"], text_color=C["muted"],
            font=fuente(20, "bold"), command=self.on_toggle)
        self.btn_ocultar.grid(row=0, column=2, rowspan=2, padx=(S.sm, 0))

        # Filete dorado: separa la marca de la navegación.
        self.separador_marca = ctk.CTkFrame(
            self, height=1, width=1, fg_color=C["gold_soft"])
        self.separador_marca.grid(
            row=0, column=0, sticky="sew", padx=S.xl, pady=(0, 0))

    def _al_clic_logo(self, _event):
        if _event.widget is self.logo and self.colapsada:
            self.on_toggle()

    def _nav_button(self, nombre, row, pady=3):
        btn = ctk.CTkButton(
            self, text=nombre, anchor="w", height=44, corner_radius=R.control,
            fg_color="transparent", hover_color=C["card"], text_color=C["text_soft"],
            font=fuente(T.cuerpo), command=lambda n=nombre: self.on_navigate(n))
        btn.grid(row=row, column=0, padx=S.md, pady=pady, sticky="ew")
        return btn

    def _build_perfil(self, row):
        datos = ajustes.cargar()
        self.perfil = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=R.tarjeta,
                                   border_width=1, border_color=C["border"])
        self.perfil.grid(row=row, column=0, sticky="sew", padx=S.md, pady=(0, S.lg))
        self.perfil.grid_columnconfigure(1, weight=1)

        Avatar(self.perfil, iniciales=ajustes.iniciales(datos.get("nombre")),
               foto=datos.get("foto", ""), lado=46
               ).grid(row=0, column=0, rowspan=3, padx=(S.md, S.sm), pady=S.md)

        estado = ctk.CTkFrame(self.perfil, fg_color="transparent")
        estado.grid(row=0, column=1, sticky="w", pady=(S.md, 0))
        punto(estado, C["ok"]).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkLabel(estado, text="EN LÍNEA", font=mono(9), text_color=C["ok"]
                     ).grid(row=0, column=1)

        self.lbl_nombre = ctk.CTkLabel(
            self.perfil, text=datos.get("nombre", ""), font=fuente(T.meta, "bold"),
            text_color=C["text"], anchor="w", justify="left")
        self.lbl_nombre.grid(row=1, column=1, sticky="ew", padx=(0, S.md))

        self.lbl_matricula = ctk.CTkLabel(
            self.perfil, text=datos.get("matricula", ""), font=mono(9),
            text_color=C["muted"], anchor="w", justify="left")
        self.lbl_matricula.grid(row=2, column=1, sticky="ew", padx=(0, S.md),
                                pady=(0, S.md))

        self.perfil.bind("<Configure>", self._ajustar_perfil, add="+")

    def _ajustar_perfil(self, event):
        ancho = max(event.width - 90, 100)
        self.lbl_nombre.configure(wraplength=ancho)
        self.lbl_matricula.configure(wraplength=ancho)

    def refrescar_perfil(self):
        """Se llama después de guardar cambios en Configuración."""
        for w in self.perfil.winfo_children():
            w.destroy()
        self.perfil.destroy()
        self._build_perfil(row=len(NAV_PRINCIPAL) + 4)
        if self.colapsada:
            self.perfil.grid_remove()

    def set_colapsada(self, colapsada):
        if self.colapsada == colapsada:
            return
        self.colapsada = colapsada
        if colapsada:
            self.configure(width=64)
            self.master.grid_columnconfigure(0, minsize=64)
            self.marca.grid_configure(padx=0, pady=(S.xl + 4, 2))
            self.marca.grid_columnconfigure(0, weight=1)
            self.logo.grid_configure(padx=0)
            self.nombre_marca.grid_remove()
            self.subtitulo_marca.grid_remove()
            self.btn_ocultar.grid_remove()
            self.separador_marca.grid_remove()
            for widget in self.items_navegacion:
                widget.grid_remove()
            self.perfil.grid_remove()
        else:
            self.configure(width=250)
            self.master.grid_columnconfigure(0, minsize=250)
            self.marca.grid_configure(padx=S.xl, pady=(S.xl + 4, 2))
            self.marca.grid_columnconfigure(0, weight=0)
            self.logo.grid_configure(padx=(0, S.md))
            self.nombre_marca.grid()
            self.subtitulo_marca.grid()
            self.btn_ocultar.grid()
            self.separador_marca.grid()
            for widget in self.items_navegacion:
                widget.grid()
            self.perfil.grid()

    def set_active(self, nombre):
        for etiqueta, btn in self.buttons.items():
            activo = etiqueta == nombre
            btn.configure(fg_color=C["accent"] if activo else "transparent",
                          text_color=C["text"] if activo else C["text_soft"])


class TopBar(ctk.CTkFrame):
    """Barra superior: ubicación actual y estado del barrido."""

    def __init__(self, master):
        super().__init__(master, height=56, corner_radius=0, fg_color=C["topbar"])
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        ruta = ctk.CTkFrame(self, fg_color="transparent")
        ruta.grid(row=0, column=0, sticky="w", padx=S.xl)
        ctk.CTkLabel(ruta, text="Portal Judicial", font=fuente(T.meta),
                     text_color=C["muted"]).grid(row=0, column=0)
        ctk.CTkLabel(ruta, text="  ›  ", font=fuente(T.meta),
                     text_color=C["dim"]).grid(row=0, column=1)
        self.lbl_seccion = ctk.CTkLabel(ruta, text="", font=fuente(T.meta, "bold"),
                                        text_color=C["text"])
        self.lbl_seccion.grid(row=0, column=2)

        derecha = ctk.CTkFrame(self, fg_color="transparent")
        derecha.grid(row=0, column=2, sticky="e", padx=S.xl)

        estado = ctk.CTkFrame(derecha, fg_color=C["card"], corner_radius=R.chip)
        estado.grid(row=0, column=0, padx=(0, S.md))
        punto(estado, C["dim"]).grid(row=0, column=0, padx=(S.md, 6), pady=7)
        ctk.CTkLabel(estado, text="SIN CONECTAR AL SAE", font=mono(T.etiqueta, "bold"),
                     text_color=C["muted"]).grid(row=0, column=1, padx=(0, S.md))

        self.lbl_barrido = ctk.CTkLabel(derecha, text="Último barrido: hoy 08:30",
                                        font=mono(T.etiqueta), text_color=C["dim"])
        self.lbl_barrido.grid(row=0, column=1)

    def set_seccion(self, nombre):
        self.lbl_seccion.configure(text=nombre)

    def set_barrido(self, texto=None):
        hora = datetime.now().strftime("%H:%M")
        self.lbl_barrido.configure(text=texto or f"Último barrido: hoy {hora}")


class LexBotApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        database.inicializar()
        aplicar_escala()               # tamaño elegido por el usuario
        self.title("LexBot SAE")
        self.geometry("1360x860")
        self.minsize(1120, 720)
        self.configure(fg_color=C["page"])

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.grid_columnconfigure(0, minsize=250)
        self.sidebar = Sidebar(
            self, on_navigate=self.mostrar, on_toggle=self._alternar_sidebar)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")

        self.topbar = TopBar(self)
        self.topbar.grid(row=0, column=1, sticky="ew")

        self.container = ctk.CTkFrame(self, fg_color=C["bg"], corner_radius=0)
        self.container.grid(row=1, column=1, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.vistas = {}
        self.actual = None
        self.detalle = None            # vista de detalle, se recrea por expediente
        self.mostrar("Dashboard")

    def _alternar_sidebar(self):
        self.sidebar.set_colapsada(not self.sidebar.colapsada)

    def _crear_vista(self, nombre):
        """Las vistas se crean la primera vez que se abren."""
        if nombre == "Dashboard":
            return DashboardView(
                self.container,
                novedades=database.novedades_para_dashboard(),
                expedientes_monitoreados=len(
                    database.listar_expedientes(solo_monitoreados=True)),
                on_sync=self._ejecutar_barrido,
                on_open_expediente=self._abrir_expediente,
                on_summarize=self._resumen_desde_dashboard,
            )
        if nombre == "Expedientes":
            return ExpedientesView(
                self.container,
                expedientes=database.listar_expedientes(solo_sae=False),
                on_open=self._abrir_expediente,
                on_monitor_change=database.actualizar_monitoreo,
                on_sync=self._sincronizar_expedientes,
                on_create=database.crear_expediente_manual,
            )
        if nombre == "LEXI":
            return LexiView(
                self.container,
                chats=database.listar_chats_lexi(),
                on_list_chats=database.listar_chats_lexi,
                on_create_chat=database.crear_chat_lexi,
                on_load_messages=database.listar_mensajes_lexi,
                on_save_message=database.guardar_mensaje_lexi,
                on_ask=self._consultar_lexi,
                on_summarize=self._resumir_novedades_ia,
                on_open_expediente=self._abrir_expediente_por_numero,
            )
        if nombre == "Alertas / Inactividad":
            return AlertasView(
                self.container,
                alertas=database.alertas_por_inactividad(),
                on_action=self._impulsar_causa,
            )
        if nombre == "Calendario de Vencimientos":
            return CalendarioView(
                self.container,
                vencimientos=database.novedades_para_calendario(),
                on_add_aviso=database.guardar_aviso_calendario,
                on_delete_aviso=database.eliminar_aviso_calendario,
                on_schedule_finding=database.agendar_hallazgo_ia,
                on_discard_finding=database.descartar_hallazgo_ia,
            )
        if nombre == "Configuración":
            return ConfiguracionView(
                self.container,
                on_save=self._guardar_configuracion,
                on_test=self._probar_conexion,
                on_perfil=self._perfil_actualizado,
            )
        raise ValueError(f"Vista desconocida: {nombre}")

    def mostrar(self, nombre):
        if self.detalle is not None:
            self.detalle.destroy()
            self.detalle = None

        if nombre not in self.vistas:
            vista = self._crear_vista(nombre)
            vista.grid(row=0, column=0, sticky="nsew")
            self.vistas[nombre] = vista
        else:
            vista = self.vistas[nombre]
            if nombre == "Dashboard":
                vista.actualizar_datos(
                    database.novedades_para_dashboard(),
                    len(database.listar_expedientes(solo_monitoreados=True)),
                )
            elif nombre == "Expedientes":
                vista.actualizar_expedientes(
                    database.listar_expedientes(solo_sae=False))
            elif nombre == "Calendario de Vencimientos":
                vista.actualizar_eventos(database.novedades_para_calendario())
            elif nombre == "Alertas / Inactividad":
                vista.actualizar_alertas(database.alertas_por_inactividad())
            elif nombre == "LEXI":
                vista.actualizar_chats(database.listar_chats_lexi())

        self.vistas[nombre].tkraise()
        self.actual = nombre
        self.sidebar.set_active(nombre)
        self.topbar.set_seccion(self._subtitulo(nombre))

    @staticmethod
    def _subtitulo(nombre):
        for clave, texto in NAV_PRINCIPAL + [NAV_PIE]:
            if clave == nombre:
                return texto
        return nombre

    # --- Detalle de expediente ---------------------------------------------
    def _abrir_expediente(self, item):
        """Abre el detalle de una causa. Se recrea en cada apertura."""
        if self.detalle is not None:
            self.detalle.destroy()

        item = dict(item)
        item["actuaciones"] = [
            {
                **actuacion,
                "fojas": "",
                "pdf": None,
            }
            for actuacion in database.listar_novedades(
                expediente=item["expediente"], solo_monitoreados=False)
        ]
        self.detalle = ExpedienteDetalleView(
            self.container,
            expediente=item,
            on_back=self._cerrar_detalle,
            on_sync=self._sincronizar_expediente,
            on_load_actuacion=self._cargar_texto_actuacion,
            on_open_expediente=self._abrir_expediente,
        )
        self.detalle.grid(row=0, column=0, sticky="nsew")
        self.detalle.tkraise()
        self.sidebar.set_active("Expedientes")
        self.topbar.set_seccion(f"Expediente {item.get('expediente', '')}")

    def _cerrar_detalle(self):
        self.mostrar("Expedientes")

    def _impulsar_causa(self, alerta):
        """Desde Alertas se abre la causa para ver el último proveído."""
        self._abrir_expediente(alerta)

    def _perfil_actualizado(self):
        """Configuración avisa que cambiaron el nombre, la matrícula o la foto."""
        self.sidebar.refrescar_perfil()
        self.sidebar.set_active(self.actual or "Configuración")

    def _ejecutar_en_segundo_plano(self, funcion, al_terminar):
        def trabajo():
            try:
                resultado = funcion()
            except Exception as exc:
                self.after(0, lambda error=exc: al_terminar(None, error))
            else:
                self.after(0, lambda valor=resultado: al_terminar(valor, None))

        threading.Thread(target=trabajo, daemon=True).start()

    @staticmethod
    def _credenciales_guardadas():
        credenciales = leer_credenciales()
        if not credenciales:
            raise ValueError(
                "Guardá las credenciales en Configuración antes de sincronizar."
            )
        return credenciales

    def _probar_conexion(self, cuit, password, al_terminar):
        def probar():
            return probar_conexion(cuit, password)

        self._ejecutar_en_segundo_plano(
            probar,
            lambda resultado, error: al_terminar(
                resultado if not error else None,
                str(error) if error else "",
            ),
        )

    def _sincronizar_expedientes(self, al_terminar):
        def sincronizar():
            credenciales = self._credenciales_guardadas()
            sincronizar_expedientes(credenciales["cuit"], credenciales["password"])
            return database.listar_expedientes(solo_sae=False)

        def terminado(expedientes, error):
            if not error:
                self._refrescar_datos_locales()
            al_terminar(expedientes, error)

        self._ejecutar_en_segundo_plano(
            sincronizar,
            terminado,
        )

    def _sincronizar_expediente(self, numero, al_terminar):
        detalle_origen = self.detalle

        def sincronizar():
            credenciales = self._credenciales_guardadas()
            return sincronizar_expediente(
                credenciales["cuit"], credenciales["password"], numero)

        def terminado(resultado, error):
            if error:
                mensaje_error = str(error)
                self.topbar.set_barrido(
                    f"Falló la actualización del exp. {numero}: {mensaje_error}")
                if self.detalle is detalle_origen:
                    al_terminar(resultado, mensaje_error)
                return

            self._refrescar_datos_locales()
            if self.detalle is detalle_origen:
                al_terminar(resultado, None)
                self._abrir_expediente(database.obtener_expediente(numero))
            self.topbar.set_barrido(f"Exp. {numero} actualizado desde el SAE")

        self._ejecutar_en_segundo_plano(sincronizar, terminado)

    def _cargar_texto_actuacion(self, numero, actuacion, al_terminar):
        detalle_origen = self.detalle

        def descargar():
            credenciales = self._credenciales_guardadas()
            return sincronizar_actuacion(
                credenciales["cuit"],
                credenciales["password"],
                numero,
                actuacion["fecha"],
                actuacion["titulo"],
            )

        def terminado(resultado, error):
            if error:
                mensaje_error = str(error)
                self.topbar.set_barrido(
                    f"Falló la actuación del exp. {numero}: {mensaje_error}")
                if self.detalle is detalle_origen:
                    al_terminar(None, mensaje_error)
                return

            self._refrescar_datos_locales()
            if self.detalle is detalle_origen:
                al_terminar(resultado, None)
            self.topbar.set_barrido(
                f"Actuación del exp. {numero} descargada desde el SAE")

        self._ejecutar_en_segundo_plano(descargar, terminado)

    def _ejecutar_barrido(self, al_terminar):
        def barrer():
            credenciales = self._credenciales_guardadas()
            return ejecutar_barrido_diario(
                credenciales["cuit"], credenciales["password"])

        def terminado(resultado, error):
            if not error:
                self._refrescar_datos_locales()
            al_terminar(resultado, str(error) if error else None)

        self._ejecutar_en_segundo_plano(barrer, terminado)

    def _refrescar_datos_locales(self):
        expedientes = database.listar_expedientes(solo_sae=False)
        if "Expedientes" in self.vistas:
            self.vistas["Expedientes"].actualizar_expedientes(expedientes)
        if "Dashboard" in self.vistas:
            self.vistas["Dashboard"].actualizar_datos(
                database.novedades_para_dashboard(),
                len(database.listar_expedientes(solo_monitoreados=True)),
            )
        if "Calendario de Vencimientos" in self.vistas:
            self.vistas["Calendario de Vencimientos"].actualizar_eventos(
                database.novedades_para_calendario())
        if "Alertas / Inactividad" in self.vistas:
            self.vistas["Alertas / Inactividad"].actualizar_alertas(
                database.alertas_por_inactividad())

    def _abrir_expediente_por_numero(self, numero):
        try:
            self._abrir_expediente(database.obtener_expediente(numero))
        except (LookupError, OSError, sqlite3.Error) as exc:
            if "LEXI" in self.vistas:
                self.vistas["LEXI"].estado.configure(
                    text=f"No se pudo abrir el expediente citado: {exc}",
                    text_color=C["error"],
                )

    def _resumen_desde_dashboard(self, periodo_dias):
        self.mostrar("LEXI")
        self.vistas["LEXI"]._iniciar_resumen(periodo_dias)

    def _consultar_lexi(self, chat_id, pregunta, al_terminar):
        def consultar():
            fuentes = database.buscar_fuentes_ia(pregunta)
            database.actualizar_estado_fuentes_ia(fuentes, "pendiente")
            try:
                servicio = OllamaService()
                respuesta = servicio.responder(pregunta, fuentes)
                evento_solicitado = respuesta.get("scheduled_event")
                if evento_solicitado:
                    evento_guardado = database.guardar_aviso_calendario(
                        evento_solicitado["date"],
                        evento_solicitado["title"],
                        evento_solicitado["time"],
                        evento_solicitado["details"],
                    )
                    respuesta["scheduled_event"] = evento_guardado
                database.guardar_mensaje_lexi(
                    chat_id, "assistant", respuesta["answer"], respuesta["sources"])
                database.actualizar_estado_fuentes_ia(fuentes, "procesada")
                return respuesta
            except Exception as exc:
                database.actualizar_estado_fuentes_ia(
                    fuentes, "fallida", type(exc).__name__)
                raise

        def terminado(respuesta, error):
            if not error and respuesta and respuesta.get("scheduled_event"):
                self._refrescar_datos_locales()
            al_terminar(respuesta, error)

        self._ejecutar_en_segundo_plano(consultar, terminado)

    def _resumir_novedades_ia(self, chat_id, periodo_dias, al_terminar):
        def resumir():
            fuentes = database.listar_fuentes_para_resumen_ia(periodo_dias)
            database.actualizar_estado_fuentes_ia(fuentes, "pendiente")
            try:
                servicio = OllamaService()
                reporte = servicio.resumir_novedades(fuentes, periodo_dias)
                texto = self._texto_reporte_ia(periodo_dias, reporte)
                database.guardar_analisis_ia(
                    periodo_dias,
                    reporte["overview"],
                    servicio.model,
                    fuentes,
                    reporte["findings"],
                )
                database.guardar_mensaje_lexi(
                    chat_id, "assistant", texto, reporte["sources"])
                database.actualizar_estado_fuentes_ia(fuentes, "procesada")
                return reporte
            except Exception as exc:
                database.actualizar_estado_fuentes_ia(
                    fuentes, "fallida", type(exc).__name__)
                raise

        def terminado(reporte, error):
            if not error:
                self._refrescar_datos_locales()
            al_terminar(reporte, error)

        self._ejecutar_en_segundo_plano(resumir, terminado)

    @staticmethod
    def _texto_reporte_ia(periodo_dias, reporte):
        partes = [
            (
                "RESUMEN DE NOVEDADES · ÚLTIMAS 24 HORAS"
                if periodo_dias == 1
                else f"RESUMEN DE NOVEDADES · ÚLTIMOS {periodo_dias} DÍAS"
            ),
            reporte["overview"],
        ]
        if reporte["findings"]:
            partes.append("HALLAZGOS PARA REVISAR")
            for hallazgo in reporte["findings"]:
                fecha = hallazgo.get("event_date") or hallazgo.get("date_text") or "sin fecha confirmada"
                partes.extend((
                    f"• {hallazgo['title']} · {fecha}",
                    hallazgo["description"],
                ))
        else:
            partes.append("No se encontraron novedades destacables en las actuaciones del período.")
        return "\n\n".join(partes)

    @staticmethod
    def _guardar_configuracion(valores, password):
        preferencias = {
            clave: valor for clave, valor in valores.items()
            if clave not in ("usuario", "frecuencia")
        }
        preferencias["frecuencia"] = valores["frecuencia"]
        database.guardar_preferencias(preferencias)


if __name__ == "__main__":
    LexBotApp().mainloop()
