import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bot_scraper
import database


class FakeSAE:
    requested = []
    requested_consultas = []
    list_calls = 0
    instances = []
    requested_limits = []
    requested_individual = []
    cases = [
        {"expediente": "123/2026", "caratula": "Caso 1", "sae_url": "https://sae/caso-1"},
        {"expediente": "456/2026", "caratula": "Caso 2", "sae_url": "https://sae/caso-2"},
    ]

    def __init__(self, cuit, password, headless=True, cases_url=None):
        self.cuit = cuit
        self.password = password
        self.headless = headless
        self.cases_url = cases_url
        self.centro_selector = None
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def iniciar_sesion(self):
        return None

    def listar_expedientes(self):
        self.list_calls += 1
        return self.cases

    def leer_actuaciones(self, url):
        self.requested.append(url)
        return self._actuaciones()

    def leer_actuaciones_por_consulta(self, centro, fuero, numero, limite=5):
        self.requested_consultas.append((centro, fuero, numero))
        self.requested_limits.append(limite)
        return self._actuaciones()

    def leer_actuacion_por_consulta(
            self, centro, fuero, numero, fecha, titulo):
        self.requested_individual.append(
            (centro, fuero, numero, fecha, titulo))
        return {**self._actuaciones()[0], "texto_completo": True}

    @staticmethod
    def _actuaciones():
        return [{
            "fecha": "2026-10-13 07:45:00",
            "tipo": "Decreto",
            "titulo": "Actuación nueva",
            "texto": "Texto completo de la actuación descargado desde el modal.",
            "texto_completo": True,
        }]


class DailySweepTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = Path(self.tempdir.name) / "lexbot.sqlite3"
        database.inicializar()
        database.guardar_expediente({
            "expediente": "123/2026", "caratula": "Caso 1", "monitorear": 0,
        }, desde_sae=True)
        database.guardar_expediente({
            "expediente": "456/2026", "caratula": "Caso 2",
            "centro_judicial": "Concepción", "fuero": "Familia y Sucesiones",
        }, desde_sae=True)
        database.actualizar_monitoreo("123/2026", False)
        FakeSAE.requested = []
        FakeSAE.requested_consultas = []
        FakeSAE.requested_limits = []
        FakeSAE.requested_individual = []
        FakeSAE.list_calls = 0
        FakeSAE.instances = []

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def test_only_monitored_linked_cases_are_opened_for_movements(self):
        with patch.object(bot_scraper, "ConectorSAE", FakeSAE):
            result = bot_scraper.ejecutar_barrido_diario("cuit", "password")

        self.assertEqual(result.expedientes_listados, 1)
        self.assertEqual(result.expedientes_revisados, 1)
        self.assertEqual(result.actuaciones_nuevas, 1)
        self.assertEqual(FakeSAE.requested, [])
        self.assertEqual(
            FakeSAE.requested_consultas,
            [("Concepción", "Familia y Sucesiones", "456/2026")],
        )
        self.assertEqual(FakeSAE.requested_limits, [5])
        self.assertEqual(FakeSAE.list_calls, 0)
        self.assertFalse(FakeSAE.instances[0].headless)
        self.assertEqual(
            database.listar_expedientes()[0]["fuente_sae"], 1)

    def test_sync_uses_consulta_for_monitored_records_only(self):
        with patch.object(bot_scraper, "ConectorSAE", FakeSAE):
            total = bot_scraper.sincronizar_expedientes("cuit", "password")

        self.assertEqual(total, 1)
        self.assertEqual(FakeSAE.list_calls, 0)
        self.assertEqual(
            FakeSAE.requested_consultas,
            [("Concepción", "Familia y Sucesiones", "456/2026")],
        )

    def test_single_case_sync_queries_and_updates_only_requested_case(self):
        with patch.object(bot_scraper, "ConectorSAE", FakeSAE):
            nuevas = bot_scraper.sincronizar_expediente(
                "cuit", "password", "456/2026")

        self.assertEqual(nuevas, 1)
        self.assertEqual(
            FakeSAE.requested_consultas,
            [("Concepción", "Familia y Sucesiones", "456/2026")],
        )
        self.assertEqual(FakeSAE.list_calls, 0)
        self.assertEqual(
            database.listar_novedades(
                solo_monitoreados=False, expediente="456/2026")[0]["titulo"],
            "Actuación nueva",
        )
        self.assertEqual(
            database.listar_novedades(
                solo_monitoreados=False, expediente="456/2026")[0]["texto"],
            "Texto completo de la actuación descargado desde el modal.",
        )
        self.assertEqual(
            database.listar_novedades(
                solo_monitoreados=False, expediente="123/2026"),
            [],
        )

    def test_single_actuation_sync_does_not_read_other_rows(self):
        with patch.object(bot_scraper, "ConectorSAE", FakeSAE):
            actualizada = bot_scraper.sincronizar_actuacion(
                "cuit", "password", "456/2026",
                "2026-10-13 07:45:00", "Actuación nueva")

        self.assertEqual(
            FakeSAE.requested_individual,
            [(
                "Concepción", "Familia y Sucesiones", "456/2026",
                "2026-10-13 07:45:00", "Actuación nueva",
            )],
        )
        self.assertEqual(FakeSAE.requested_consultas, [])
        self.assertTrue(actualizada["texto_completo"])
        almacenada = database.listar_novedades(
            solo_monitoreados=False, expediente="456/2026")[0]
        self.assertEqual(almacenada["texto"], actualizada["texto"])
        self.assertEqual(almacenada["texto_completo"], 1)

    def test_manually_added_case_with_center_and_fuero_uses_consulta_route(self):
        database.crear_expediente_manual({
            "expediente": "789/2026",
            "centro_judicial": "cAPiTaL",
            "fuero": "cIvIl y CoMeRcIaL CoMúN",
        })
        with patch.object(bot_scraper, "ConectorSAE", FakeSAE):
            result = bot_scraper.ejecutar_barrido_diario("cuit", "password")

        self.assertEqual(result.expedientes_revisados, 2)
        self.assertEqual(FakeSAE.requested, [])
        self.assertEqual(
            FakeSAE.requested_consultas,
            [
                ("Concepción", "Familia y Sucesiones", "456/2026"),
                ("cAPiTaL", "cIvIl y CoMeRcIaL CoMúN", "789/2026"),
            ],
        )
        manual = next(
            item for item in database.listar_expedientes()
            if item["expediente"] == "789/2026"
        )
        self.assertEqual(manual["fuente_sae"], 1)

    def test_active_case_without_consulta_fields_fails_instead_of_using_url(self):
        with self.assertRaisesRegex(
            bot_scraper.ErrorPortalSAE,
            "no tiene centro judicial, fuero",
        ):
            bot_scraper._leer_actuaciones(FakeSAE("cuit", "password"), {
                "expediente": "999/2026",
                "sae_url": "https://sae.test/999",
            })
