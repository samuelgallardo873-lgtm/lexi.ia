"""Conector Playwright para consultar causas en el SAE de Tucumán."""

from dataclasses import dataclass
from datetime import datetime
import os
import re

SAE_LOGIN_URL = os.environ.get(
    "LEXBOT_SAE_LOGIN_URL", "https://login.justucuman.gov.ar/"
)
SAE_CONSULTA_URL = "https://consultaexpedientes.justucuman.gov.ar/"
TIMEOUT_MS = 25000


class ErrorPortalSAE(RuntimeError):
    """La página del SAE no tiene la estructura esperada o no responde."""


class CredencialesInvalidas(ErrorPortalSAE):
    """El portal rechazó el inicio de sesión."""


@dataclass(frozen=True)
class ResultadoConexion:
    exito: bool
    estado: str
    mensaje: str


class ConectorSAE:
    """Mantiene una sesión autenticada y permite leer causas y actuaciones."""

    def __init__(self, cuit, password, headless=True):
        if not cuit.strip() or not password:
            raise ValueError("CUIT y contraseña son obligatorios.")
        self.cuit = cuit.strip()
        self.password = password
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Falta Playwright. Instalalo con 'pip install playwright' y "
                "'playwright install chromium'."
            ) from exc

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_default_timeout(TIMEOUT_MS)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def iniciar_sesion(self):
        self.page.goto(SAE_LOGIN_URL, wait_until="domcontentloaded")
        usuario = self.page.locator("#cuit, input[name='username']").first
        password = self.page.locator("#password, input[name='password']").first
        if not usuario.count() or not password.count():
            raise ErrorPortalSAE("No se reconoció el formulario oficial de acceso al SAE.")
        usuario.fill(self.cuit)
        password.fill(self.password)
        boton = self.page.locator(
            "form button[type='submit'], form input[type='submit']"
        ).first
        if not boton.count():
            raise ErrorPortalSAE("El formulario del SAE no contiene un botón de acceso.")
        boton.click()
        self.page.wait_for_timeout(2000)
        self.page.goto(SAE_CONSULTA_URL, wait_until="networkidle")
        if not self._hay_boton_centro_judicial_visible():
            raise ErrorPortalSAE(
                "Se abrió la consulta del SAE, pero no se encontró visible ningún "
                "botón de Centro Judicial. Verificá la autenticación y la página "
                f"actual: {self.page.url}."
            )

    def _hay_boton_centro_judicial_visible(self):
        for texto in (
            "CAPITAL", "Centro Judicial CAPITAL",
            "CONCEPCIÓN", "Centro Judicial CONCEPCIÓN",
            "MONTEROS", "Centro Judicial MONTEROS",
            "ESTE", "Centro Judicial ESTE",
            "PAZ", "Centro Judicial PAZ",
        ):
            if self._buscar_texto_visible(texto, dentro=self.page, solo_boton=True):
                return True
        return False

    def abrir_consulta_expedientes(self):
        """Abre la consulta de causas en el portal público autenticado."""
        self.page.goto(SAE_CONSULTA_URL, wait_until="domcontentloaded")

    def leer_actuaciones(self, url):
        if not url:
            raise ErrorPortalSAE("El expediente no tiene un enlace de detalle en el SAE.")
        self.page.goto(url, wait_until="domcontentloaded")
        return self._leer_actuaciones_actuales()

    def leer_actuaciones_por_consulta(
            self, centro_judicial, fuero, numero_expediente, limite=5):
        """Lee el texto modal de las actuaciones más recientes de una causa."""
        self._abrir_historia_por_consulta(
            centro_judicial, fuero, numero_expediente)
        return self._leer_actuaciones_actuales(limite=limite)

    def leer_actuacion_por_consulta(
            self, centro_judicial, fuero, numero_expediente, fecha, titulo):
        """Lee solo el modal de la actuación indicada en la historia SAE."""
        self._abrir_historia_por_consulta(
            centro_judicial, fuero, numero_expediente)
        return self._leer_actuacion_actual(fecha, titulo)

    def _abrir_historia_por_consulta(
            self, centro_judicial, fuero, numero_expediente):
        centro = self._centro_visible(centro_judicial)
        fuero = str(fuero).strip()
        numero = str(numero_expediente).strip()
        if not centro or not fuero or not numero:
            raise ValueError("Centro judicial, fuero y número de expediente son obligatorios.")

        self.abrir_consulta_expedientes()
        selector_centro = f"text=/{re.escape(centro)}/i"
        self.page.locator(selector_centro).first.click(force=True)
        self._esperar_modal_fueros()
        self.page.wait_for_timeout(1000)
        selector_fuero = f"text=/{re.escape(fuero)}/i"
        self.page.locator(selector_fuero).first.click(force=True)
        self.page.wait_for_timeout(2000)

        input_expt = self.page.locator(
            "input[placeholder*='Ej'], input[placeholder*='1/20']"
        ).first
        input_expt.wait_for(state="visible", timeout=10000)
        input_expt.fill(numero)
        input_expt.press("Enter")
        self.page.wait_for_selector(
            "table tbody tr, .table tr",
            timeout=15000,
        )
        self.page.wait_for_timeout(1000)

        fila = self._fila_resultado(numero)
        if fila is None:
            raise ErrorPortalSAE(
                f"La consulta SAE no devolvió una fila para el expediente {numero} "
                f"({centro} / {fuero})."
            )
        self._abrir_detalle_fila(fila)
        self.page.wait_for_url("**/historia", timeout=15000)
        self.page.wait_for_load_state("domcontentloaded")

    def _tabla_actuaciones_actual(self):
        tablas = self.page.locator("table").all()
        for tabla in tablas:
            datos = tabla.evaluate("""table => {
                const rows = [...table.querySelectorAll('tr')];
                const head = rows.length
                    ? [...rows[0].querySelectorAll('th, td')].map(c => c.innerText.trim())
                    : [];
                return {head, rows: rows.slice(1).map(row =>
                    [...row.querySelectorAll('th, td')].map(cell => cell.innerText.trim()))};
            }""")
            encabezado = " ".join(datos["head"]).lower()
            if not any(palabra in encabezado for palabra in
                       ("actuación", "actuacion", "proveído", "proveido",
                        "movimiento", "descripción", "descripcion")):
                continue
            filas = tabla.locator("tbody tr").all()
            if len(filas) == len(datos["rows"]) + 1:
                filas = filas[1:]
            if len(filas) != len(datos["rows"]):
                raise ErrorPortalSAE(
                    "No se pudieron asociar las filas de actuaciones con sus "
                    f"controles de detalle en {self.page.url}."
                )
            return datos["head"], datos["rows"], filas
        raise ErrorPortalSAE(
            f"No se encontró la tabla de actuaciones del expediente en {self.page.url}."
        )

    def _leer_actuaciones_actuales(self, limite=5):
        headers, rows, filas = self._tabla_actuaciones_actual()
        movimientos = []
        for fila, celdas in zip(filas, rows):
            movimiento = self._normalizar_actuaciones(headers, [celdas])
            if movimiento:
                movimientos.append((fila, movimiento[0]))
        movimientos.sort(
            key=lambda item: item[1]["fecha"],
            reverse=True,
        )

        actuaciones = []
        for fila, actuacion in movimientos[:limite]:
            actuacion["texto"] = self._leer_texto_completo_actuacion(fila)
            actuacion["texto_completo"] = True
            actuaciones.append(actuacion)
        return actuaciones

    def _leer_actuacion_actual(self, fecha, titulo):
        headers, rows, filas = self._tabla_actuaciones_actual()
        fecha_objetivo = self._normalizar_fecha(str(fecha))
        titulo_objetivo = self._normalizar_clave_texto(titulo)
        for fila, celdas in zip(filas, rows):
            movimiento = self._normalizar_actuaciones(headers, [celdas])
            if not movimiento:
                continue
            actual = movimiento[0]
            if (
                actual["fecha"] != fecha_objetivo
                or self._normalizar_clave_texto(actual["titulo"]) != titulo_objetivo
            ):
                continue
            actual["texto"] = self._leer_texto_completo_actuacion(fila)
            actual["texto_completo"] = True
            return actual
        raise ErrorPortalSAE(
            f"No se encontró la actuación {titulo!r} del {fecha!r} "
            "en la historia del expediente."
        )

    @staticmethod
    def _normalizar_clave_texto(texto):
        return " ".join(str(texto).split()).casefold()

    def _leer_texto_completo_actuacion(self, fila):
        boton_detalle = fila.locator(
            "td:last-child button, td:last-child a"
        ).first
        boton_detalle.wait_for(state="visible", timeout=15000)
        boton_detalle.click(force=True)

        modal = self.page.locator(
            '[role="dialog"]:visible, .modal.show, .modal:visible'
        ).last
        modal.wait_for(state="visible", timeout=15000)
        cuerpo = modal.locator(".modal-body").first
        if not cuerpo.count():
            raise ErrorPortalSAE(
                "Se abrió el detalle de la actuación, pero no se encontró "
                "el contenido del modal."
            )
        cuerpo.wait_for(state="visible", timeout=15000)
        self.page.wait_for_function(
            """() => [...document.querySelectorAll(
                '.modal.show, [role="dialog"]'
            )].some(modal => {
                const contenido = modal.querySelector('.modal-body');
                return modal.getClientRects().length &&
                    getComputedStyle(modal).visibility !== 'hidden' &&
                    contenido && contenido.innerText.trim().length > 0;
            })""",
            timeout=15000,
        )
        texto = cuerpo.inner_text().strip()
        if not texto:
            contenido_modal = modal.locator(".modal-content").first
            contenido_modal.wait_for(state="visible", timeout=15000)
            texto = contenido_modal.inner_text().strip()
        if not texto:
            raise ErrorPortalSAE(
                "El modal de la actuación se abrió sin información para guardar."
            )

        cerrar = modal.locator(
            "button[data-dismiss='modal'], button[data-bs-dismiss='modal'], "
            ".modal-header button.close, [aria-label='Close'], "
            "[aria-label='Cerrar']"
        ).first
        if not cerrar.count():
            cerrar = modal.get_by_role(
                "button", name=re.compile(r"cerrar|close|×", re.IGNORECASE)
            ).first
        if not cerrar.count():
            raise ErrorPortalSAE(
                "No se encontró el botón para cerrar el detalle de la actuación."
            )
        cerrar.click(force=True)
        modal.wait_for(state="hidden", timeout=15000)
        return texto

    def _buscar_texto_visible(self, texto, dentro, solo_boton=False):
        raiz = dentro
        patron = re.compile(re.escape(texto), re.IGNORECASE)
        if solo_boton:
            elemento = raiz.get_by_role("button", name=patron).first
            if elemento.count() and elemento.is_visible():
                return elemento
            return None

        elemento = raiz.get_by_role("button", name=patron).first
        if elemento.count() and elemento.is_visible():
            return elemento
        elemento = raiz.get_by_text(texto, exact=False).first
        if elemento.count() and elemento.is_visible():
            return elemento
        return None

    def _click_por_texto(self, texto, descripcion, dentro=None, solo_boton=False):
        raiz = dentro if dentro is not None else self.page
        elemento = self._buscar_texto_visible(texto, raiz, solo_boton=solo_boton)
        if elemento is not None:
            elemento.click()
            return
        raise ErrorPortalSAE(
            f"No se encontró {descripcion} en la página SAE actual ({self.page.url})."
        )

    def _esperar_modal_fueros(self):
        modal = self.page.locator(
            '[role="dialog"]:visible, .modal.show, .modal:visible'
        ).last
        modal.wait_for(state="visible", timeout=TIMEOUT_MS)
        return modal

    def _fila_resultado(self, numero):
        numero_normalizado = re.sub(r"\s+", "", numero).casefold()
        for fila in self.page.locator("tr").all():
            texto = re.sub(r"\s+", "", fila.inner_text()).casefold()
            if numero_normalizado in texto and fila.is_visible():
                return fila
        return None

    def _abrir_detalle_fila(self, fila):
        boton_historia = fila.locator("button.btn.btn-info.btn-sm").first
        boton_historia.wait_for(state="visible", timeout=15000)
        boton_historia.click(force=True)

    @staticmethod
    def _centro_visible(centro):
        return str(centro).strip()

    @staticmethod
    def _indice(headers, terminos):
        for index, header in enumerate(headers):
            if any(termino in header for termino in terminos):
                return index
        return None

    @staticmethod
    def _celda(cells, index):
        return cells[index].strip() if index is not None and index < len(cells) else ""

    @classmethod
    def _normalizar_actuaciones(cls, headers, rows):
        normalized_headers = [header.lower() for header in headers]
        fecha_idx = cls._indice(normalized_headers, ("fecha",))
        tipo_idx = cls._indice(normalized_headers, ("tipo", "clase"))
        texto_idx = cls._indice(
            normalized_headers,
            ("actuación", "actuacion", "proveído", "proveido", "movimiento",
             "descripción", "descripcion", "detalle"),
        )
        if fecha_idx is None:
            raise ErrorPortalSAE("La tabla de actuaciones no expone una columna Fecha.")
        if texto_idx is None:
            texto_idx = next((i for i in range(len(headers)) if i != fecha_idx), None)
        actuaciones = []
        for row in rows:
            fecha_raw = cls._celda(row, fecha_idx)
            contenido = cls._celda(row, texto_idx)
            if not fecha_raw or not contenido:
                continue
            fecha = cls._normalizar_fecha(fecha_raw)
            if not fecha:
                raise ErrorPortalSAE(f"No se pudo interpretar la fecha de actuación: {fecha_raw}")
            tipo = cls._celda(row, tipo_idx) or "Actuación"
            actuaciones.append({
                "fecha": fecha,
                "tipo": tipo,
                "titulo": contenido[:240],
                "texto": contenido,
            })
        return actuaciones

    @staticmethod
    def _normalizar_fecha(texto):
        texto = " ".join(texto.split())
        formatos = (
            "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
        )
        for formato in formatos:
            try:
                return datetime.strptime(texto, formato).isoformat(sep=" ")
            except ValueError:
                continue
        return ""


def probar_conexion(cuit, password):
    """Prueba las credenciales y distingue un rechazo del SAE de errores técnicos."""
    try:
        with ConectorSAE(cuit, password) as sae:
            sae.iniciar_sesion()
    except CredencialesInvalidas as exc:
        return ResultadoConexion(False, "Credenciales inválidas", str(exc))
    return ResultadoConexion(True, "Éxito", "Inicio de sesión en el SAE correcto.")
