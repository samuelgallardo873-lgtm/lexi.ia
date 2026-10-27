import unittest

from sae_connector import ConectorSAE, ErrorPortalSAE


class DateAndActuationParsingTests(unittest.TestCase):
    def test_successful_login_navigates_to_direct_consulta_url(self):
        class Locator:
            first = None

            def __init__(self, page, count=1, visible=True):
                self.page = page
                self.first = self
                self.count_value = count
                self.visible = visible

            def count(self):
                return self.count_value

            def fill(self, _value):
                return None

            def click(self):
                self.page.url = "https://portal.justucuman.gov.ar/inicio"

            def is_visible(self):
                return self.visible

            def all_inner_texts(self):
                return []

        class Page:
            url = "https://login.justucuman.gov.ar/"

            def __init__(self):
                self.goto_urls = []
                self.waits = []

            def goto(self, url, **kwargs):
                self.goto_urls.append((url, kwargs))
                self.url = url

            def locator(self, _selector):
                return Locator(self)

            def wait_for_timeout(self, duration):
                self.waits.append(duration)

            def get_by_role(self, role, name=None, exact=False):
                if role == "button" and name and name.search("Centro Judicial CAPITAL"):
                    return Locator(self)
                return Locator(self, count=0, visible=False)

        connector = ConectorSAE("cuit", "password")
        connector.page = Page()

        connector.iniciar_sesion()

        self.assertEqual(
            connector.page.goto_urls,
            [
                ("https://login.justucuman.gov.ar/", {"wait_until": "domcontentloaded"}),
                (
                    "https://consultaexpedientes.justucuman.gov.ar/",
                    {"wait_until": "networkidle"},
                ),
            ],
        )
        self.assertEqual(connector.page.waits, [2000])

    def test_portal_date_is_normalized_for_sqlite(self):
        self.assertEqual(
            ConectorSAE._normalizar_fecha("13/10/2026 07:45"),
            "2026-10-13 07:45:00",
        )

    def test_movement_rows_are_parsed_without_inventing_deadlines(self):
        actuaciones = ConectorSAE._normalizar_actuaciones(
            ["Fecha", "Tipo", "Actuación"],
            [["13/10/2026 07:45", "Decreto", "Córrase traslado."]],
        )

        self.assertEqual(actuaciones[0]["fecha"], "2026-10-13 07:45:00")
        self.assertEqual(actuaciones[0]["titulo"], "Córrase traslado.")
        self.assertNotIn("limite", actuaciones[0])

    def test_unrecognized_movement_date_fails_explicitly(self):
        with self.assertRaises(ErrorPortalSAE):
            ConectorSAE._normalizar_actuaciones(
                ["Fecha", "Actuación"],
                [["ayer", "Córrase traslado."]],
            )

    def test_consulta_flow_selects_center_fuero_and_expediente(self):
        class Locator:
            def __init__(self, page, name="", exists=True, is_modal=False):
                self.page = page
                self.name = name
                self.exists = exists
                self.modal = is_modal
                self.first = self
                self.last = self
                self.force_click = False
                self.wait_calls = []

            def count(self):
                return int(self.exists)

            def is_visible(self):
                return self.exists

            def click(self, force=False):
                self.force_click = force
                self.page.actions.append(self.name)
                if self.name.casefold() == "capital":
                    self.page.modal_open = True
                elif self.name == "VER HISTORIA":
                    self.page.url = (
                        "https://consultaexpedientes.justucuman.gov.ar/"
                        "familia/expediente/12392%2F21/historia"
                    )
                elif self.name == "lupa":
                    self.page.modal_open = True
                elif self.name == "cerrar":
                    self.page.modal_open = False

            def fill(self, value):
                self.page.actions.append(f"fill:{value}")

            def press(self, key):
                self.page.actions.append(f"press:{key}")

            def inner_text(self):
                if self.name == "modal-body":
                    return (
                        "El escrito seleccionado no contiene texto.\n"
                        "Actuación firmada en fecha: 02/03/2026"
                    )
                return "Exp. 12392/21"

            def get_by_role(self, role, name=None, exact=False):
                labels = ("CAPITAL", "Familia y Sucesiones", "Buscar")
                label = next(
                    (item for item in labels
                     if self.modal and role == "button" and name and name.search(item)),
                    None,
                )
                if label:
                    return Locator(self.page, label)
                return Locator(self.page, exists=False)

            def get_by_text(self, text, exact=False):
                if self.modal and not exact and text.casefold() == "familia y sucesiones":
                    return Locator(self.page, "Familia y Sucesiones")
                return Locator(self.page, exists=False)

            def locator(self, selector):
                self.page.selectors.append(selector)
                if (
                    self.name == "result-row"
                    and selector == "button.btn.btn-info.btn-sm"
                ):
                    return self.page.history_button
                if (
                    self.name == "movement-row"
                    and selector == "td:last-child button, td:last-child a"
                ):
                    return self.page.detail_button
                if self.name == "modal" and selector == ".modal-body":
                    return Locator(
                        self.page, "modal-body", exists=self.page.modal_open)
                if self.name == "modal" and selector.startswith(
                    "button[data-dismiss="
                ):
                    return Locator(
                        self.page, "cerrar", exists=self.page.modal_open)
                if self.name == "movement-table" and selector == "tbody tr":
                    self.page.selectors.append(selector)
                    return LocatorList([self.page.movement_row])
                return Locator(self.page, exists=False)

            def wait_for(self, state, timeout):
                self.wait_calls.append((state, timeout))
                visible = (
                    self.page.modal_open if self.name == "modal" else self.exists
                )
                if state == "visible" and not visible:
                    raise AssertionError("Expected a visible locator")
                if state == "hidden" and visible:
                    raise AssertionError("Expected a hidden locator")

            def all(self):
                return []

            def evaluate(self, _script):
                return {
                    "head": ["Fecha", "Descripción"],
                    "rows": [["13/10/2026 07:45", "Córrase traslado"]],
                }

        class Page:
            def __init__(self):
                self.url = "https://sae.test/consulta"
                self.actions = []
                self.selectors = []
                self.function_wait_calls = []
                self.modal_open = False
                self.center_locator = Locator(self, "capital")
                self.fuero_locator = Locator(self, "Familia y Sucesiones")
                self.input_locator = Locator(self, "numero")
                self.search_button = Locator(self, "search-button")
                self.result_row = Locator(self, "result-row")
                self.history_button = Locator(self, "VER HISTORIA")
                self.movement_row = Locator(self, "movement-row")
                self.detail_button = Locator(self, "lupa")
                self.table = Locator(self, "movement-table")

            def get_by_role(self, role, name=None, exact=False):
                labels = ("CAPITAL", "Familia y Sucesiones", "Buscar")
                label = next(
                    (item for item in labels
                     if role == "button" and name and name.search(item)),
                    None,
                )
                if label:
                    return Locator(self, label)
                return Locator(self, exists=False)

            def get_by_text(self, text, exact=False):
                if not exact and text.casefold() == "capital":
                    return Locator(self, "CAPITAL")
                return Locator(self, exists=False)

            def get_by_label(self, _name):
                return Locator(self, "numero")

            def get_by_placeholder(self, _name):
                return Locator(self, exists=False)

            def locator(self, selector):
                self.selectors.append(selector)
                if selector == (
                    "input[placeholder*='Ej'], input[placeholder*='1/20']"
                ):
                    return LocatorList([self.input_locator])
                if selector == "button.btn.btn-info.btn-sm":
                    return LocatorList([self.history_button])
                if selector.startswith("text=/"):
                    pattern = selector[len("text=/"):-2]
                    if pattern.casefold() == "capital":
                        return LocatorList([self.center_locator])
                    if pattern.replace("\\ ", " ").casefold() == (
                            "familia y sucesiones"):
                        return LocatorList([self.fuero_locator])
                if selector == (
                    '[role="dialog"]:visible, .modal.show, .modal:visible'
                ):
                    return Locator(
                        self, "modal", exists=self.modal_open, is_modal=True)
                if selector == "tr":
                    return LocatorList([self.result_row])
                if selector == "table":
                    return LocatorList([self.table])
                return Locator(self, exists=False)

            def goto(self, url, **_kwargs):
                self.actions.append(f"goto:{url}")
                self.url = url

            def wait_for_load_state(self, _state):
                return None

            def wait_for_url(self, url, timeout):
                self.actions.append(f"wait_for_url:{url}:{timeout}")
                if not self.url.endswith("/historia"):
                    raise AssertionError("Expected history-page navigation")

            def wait_for_function(self, _expression, timeout):
                self.function_wait_calls.append(timeout)
                self.actions.append(f"wait_for_modal_text:{timeout}")

            def wait_for_selector(self, selector, timeout):
                self.actions.append(f"wait_for_selector:{selector}:{timeout}")

            def wait_for_timeout(self, duration):
                self.actions.append(f"wait:{duration}")

        class LocatorList:
            def __init__(self, locators):
                self.locators = locators

            @property
            def first(self):
                return self.locators[0]

            def all(self):
                return self.locators

        connector = ConectorSAE("cuit", "password")
        connector.page = Page()

        actuaciones = connector.leer_actuaciones_por_consulta(
            "capital",
            "familia y sucesiones",
            "12392/21",
        )

        self.assertTrue(connector.page.center_locator.force_click)
        self.assertTrue(connector.page.fuero_locator.force_click)
        self.assertEqual(
            connector.page.input_locator.wait_calls,
            [("visible", 10000)],
        )
        self.assertIn(
            "input[placeholder*='Ej'], input[placeholder*='1/20']",
            connector.page.selectors,
        )
        self.assertEqual(
            connector.page.history_button.wait_calls,
            [("visible", 15000)],
        )
        self.assertTrue(connector.page.history_button.force_click)
        self.assertEqual(
            connector.page.actions[
                connector.page.actions.index("press:Enter") + 1:
            ],
            [
                "wait_for_selector:table tbody tr, .table tr:15000",
                "wait:1000",
                "VER HISTORIA",
                "wait_for_url:**/historia:15000",
                "lupa",
                "wait_for_modal_text:15000",
                "cerrar",
            ],
        )
        self.assertIn(
            "button.btn.btn-info.btn-sm",
            connector.page.selectors,
        )
        self.assertIn("text=/capital/i", connector.page.selectors)
        self.assertIn(r"text=/familia\ y\ sucesiones/i", connector.page.selectors)
        self.assertEqual(
            connector.page.actions,
            [
                "goto:https://consultaexpedientes.justucuman.gov.ar/",
                "capital",
                "wait:1000",
                "Familia y Sucesiones",
                "wait:2000",
                "fill:12392/21",
                "press:Enter",
                "wait_for_selector:table tbody tr, .table tr:15000",
                "wait:1000",
                "VER HISTORIA",
                "wait_for_url:**/historia:15000",
                "lupa",
                "wait_for_modal_text:15000",
                "cerrar",
            ],
        )
        self.assertTrue(connector.page.url.endswith("/historia"))
        self.assertEqual(actuaciones[0]["titulo"], "Córrase traslado")
        self.assertEqual(
            actuaciones[0]["texto"],
            "El escrito seleccionado no contiene texto.\n"
            "Actuación firmada en fecha: 02/03/2026",
        )
        self.assertTrue(connector.page.detail_button.force_click)
        self.assertIn(
            "td:last-child button, td:last-child a",
            connector.page.selectors,
        )
        self.assertEqual(connector.page.function_wait_calls, [15000])
        self.assertFalse(connector.page.modal_open)

    def test_recent_history_reads_only_the_five_first_rows(self):
        connector = ConectorSAE("cuit", "password")
        rows = [
            [f"{day:02d}/03/2026", f"Movimiento {day}"]
            for day in (10, 5, 8, 6, 9, 7)
        ]
        clicked = []
        connector._tabla_actuaciones_actual = lambda: (
            ["Fecha", "Descripción"],
            rows,
            list(range(len(rows))),
        )
        connector._leer_texto_completo_actuacion = lambda row: (
            clicked.append(row) or f"Texto completo {row}"
        )

        actuaciones = connector._leer_actuaciones_actuales()

        self.assertEqual(len(actuaciones), 5)
        self.assertEqual(clicked, [0, 4, 2, 5, 3])
        self.assertEqual(
            [item["titulo"] for item in actuaciones],
            [
                "Movimiento 10",
                "Movimiento 9",
                "Movimiento 8",
                "Movimiento 7",
                "Movimiento 6",
            ],
        )
        self.assertTrue(all(item["texto_completo"] for item in actuaciones))

    def test_requested_old_actuation_reads_only_matching_modal(self):
        connector = ConectorSAE("cuit", "password")
        rows = [
            ["13/10/2026", "Movimiento reciente"],
            ["10/03/2026", "OFICIO BANCO MACRO"],
        ]
        clicked = []
        connector._tabla_actuaciones_actual = lambda: (
            ["Fecha", "Descripción"],
            rows,
            ["recent-row", "requested-row"],
        )
        connector._leer_texto_completo_actuacion = lambda row: (
            clicked.append(row) or
            "OFICIO BANCO MACRO\\nActuación firmada en fecha: 10/03/2026"
        )

        actuacion = connector._leer_actuacion_actual(
            "2026-03-10 00:00:00", "OFICIO BANCO MACRO")

        self.assertEqual(clicked, ["requested-row"])
        self.assertEqual(actuacion["titulo"], "OFICIO BANCO MACRO")
        self.assertIn("Actuación firmada", actuacion["texto"])
        self.assertTrue(actuacion["texto_completo"])


if __name__ == "__main__":
    unittest.main()
