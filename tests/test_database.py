import tempfile
import unittest
from datetime import date
from pathlib import Path
import sqlite3

import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = Path(self.tempdir.name) / "lexbot.sqlite3"
        database.inicializar()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.tempdir.cleanup()

    def test_new_expedients_are_monitored_by_default_and_can_be_disabled(self):
        database.guardar_expediente({
            "expediente": "123/2026",
            "caratula": "Pérez s/ prueba",
        }, desde_sae=True)

        expediente = database.listar_expedientes()[0]
        self.assertEqual(expediente["monitorear"], 1)

        database.actualizar_monitoreo("123/2026", False)
        self.assertEqual(database.listar_expedientes()[0]["monitorear"], 0)
        self.assertEqual(database.listar_expedientes(solo_monitoreados=True), [])

    def test_expedients_not_imported_from_sae_are_not_listed(self):
        database.guardar_expediente({
            "expediente": "123/2026",
            "caratula": "Caso local",
        })

        self.assertEqual(database.listar_expedientes(), [])
        self.assertEqual(database.listar_expedientes(solo_sae=False)[0]["expediente"],
                         "123/2026")

    def test_manual_expedient_is_saved_immediately_and_starts_monitored(self):
        expediente = database.crear_expediente_manual({
            "expediente": "12392/21",
            "caratula": "García c/ Sucesión",
            "fuero": "Familia y Sucesiones",
            "centro_judicial": "Capital",
        })

        self.assertEqual(expediente["monitorear"], 1)
        self.assertEqual(expediente["fuente_sae"], 0)
        self.assertEqual(expediente["centro_judicial"], "Capital")
        self.assertEqual(database.listar_expedientes(solo_sae=False), [expediente])
        self.assertEqual(database.listar_expedientes(), [])

    def test_manual_expedient_rejects_duplicate_number(self):
        datos = {"expediente": "12392/21", "centro_judicial": "Capital"}
        database.crear_expediente_manual(datos)

        with self.assertRaisesRegex(ValueError, "ya está registrado"):
            database.crear_expediente_manual(datos)

    def test_novedades_are_deduplicated_and_hidden_when_monitoring_is_off(self):
        database.guardar_expediente({
            "expediente": "123/2026",
            "caratula": "Pérez s/ prueba",
            "fuero": "Civil",
        }, desde_sae=True)
        actuacion = {
            "expediente": "123/2026",
            "fecha": "2026-10-13 07:45:00",
            "tipo": "Decreto",
            "titulo": "Traslado",
            "texto": "Córrase traslado por cinco días.",
        }

        self.assertTrue(database.guardar_novedad(actuacion))
        self.assertFalse(database.guardar_novedad(actuacion))
        self.assertEqual(len(database.novedades_para_dashboard()), 1)
        self.assertEqual(len(database.novedades_para_calendario()), 1)

        database.actualizar_monitoreo("123/2026", False)
        self.assertEqual(database.novedades_para_dashboard(), [])
        self.assertEqual(database.novedades_para_calendario(), [])

    def test_full_text_enriches_previously_saved_short_movement(self):
        database.guardar_expediente({
            "expediente": "123/2026",
            "caratula": "Pérez s/ prueba",
            "fuero": "Civil",
        }, desde_sae=True)
        base = {
            "expediente": "123/2026",
            "fecha": "2026-10-13 07:45:00",
            "tipo": "Decreto",
            "titulo": "Córrase traslado",
        }
        self.assertTrue(database.guardar_novedad({
            **base,
            "texto": "Córrase traslado. Resumen corto del portal.",
        }))

        self.assertFalse(database.guardar_novedad({
            **base,
            "texto_completo": True,
            "texto": "Córrase traslado\n\nConsiderando los antecedentes...\nFirmado.",
        }))

        novedades = database.listar_novedades(solo_monitoreados=False)
        self.assertEqual(len(novedades), 1)
        self.assertEqual(
            novedades[0]["texto"],
            "Córrase traslado\n\nConsiderando los antecedentes...\nFirmado.",
        )
        self.assertEqual(novedades[0]["texto_completo"], 1)

    def test_office_is_extracted_from_full_actuation_and_kept_on_expedient(self):
        database.guardar_expediente({
            "expediente": "2993/13",
            "caratula": "Ruiz Yolanda Irma c/ s/ Sucesión",
        }, desde_sae=True)

        database.guardar_novedad({
            "expediente": "2993/13",
            "fecha": "2026-10-13 09:00:00",
            "tipo": "Actuación",
            "titulo": "Decreto",
            "texto": (
                "PODER JUDICIAL DE TUCUMÁN\n\n"
                "OFICINA DE GESTIÓN ASOCIADA DE SUCESIONES N° 1\n\n"
                "Se dispone el trámite correspondiente."
            ),
            "texto_completo": True,
        })

        expediente = database.listar_expedientes()[0]
        self.assertEqual(
            expediente["oficina"],
            "OFICINA DE GESTIÓN ASOCIADA DE SUCESIONES N° 1",
        )

        database.guardar_expediente({
            "expediente": "2993/13",
            "caratula": "Ruiz Yolanda Irma c/ s/ Sucesión",
        }, desde_sae=True)
        expediente_actualizado = database.listar_expedientes()[0]
        self.assertEqual(expediente_actualizado["oficina"], expediente["oficina"])

    def test_dashboard_shows_only_the_latest_movement_per_expedient(self):
        for numero in ("123/2026", "456/2026"):
            database.guardar_expediente({
                "expediente": numero,
                "caratula": f"Causa {numero}",
                "fuero": "Civil",
            }, desde_sae=True)
        actuaciones = (
            ("123/2026", "2026-10-10 09:00:00", "Movimiento anterior"),
            ("123/2026", "2026-10-11 09:00:00", "Movimiento reciente"),
            ("456/2026", "2026-10-12 09:00:00", "Otra causa"),
        )
        for numero, fecha, titulo in actuaciones:
            database.guardar_novedad({
                "expediente": numero,
                "fecha": fecha,
                "tipo": "Decreto",
                "titulo": titulo,
                "texto": titulo,
            })

        dashboard = database.novedades_para_dashboard()

        self.assertEqual(len(dashboard), 2)
        self.assertEqual(
            {item["expediente"]: item["titulo"] for item in dashboard},
            {
                "123/2026": "Movimiento reciente",
                "456/2026": "Otra causa",
            },
        )
        self.assertEqual(
            len(database.listar_novedades(solo_monitoreados=False)), 3)

    def test_lexi_chat_and_messages_are_persisted_and_load_in_order(self):
        chat_id = database.crear_chat_lexi()
        database.guardar_mensaje_lexi(
            chat_id, "user", "  ¿Qué pasó con el expediente 12392/21?  "
        )
        database.guardar_mensaje_lexi(
            chat_id, "assistant", "La última actuación fue un decreto."
        )

        chats = database.listar_chats_lexi()
        mensajes = database.listar_mensajes_lexi(chat_id)

        self.assertEqual(chats[0]["id"], chat_id)
        self.assertEqual(chats[0]["titulo"], "¿Qué pasó con el expediente 12392/21?")
        self.assertEqual(
            [(mensaje["rol"], mensaje["contenido"]) for mensaje in mensajes],
            [
                ("user", "¿Qué pasó con el expediente 12392/21?"),
                ("assistant", "La última actuación fue un decreto."),
            ],
        )

        database.inicializar()
        self.assertEqual(len(database.listar_mensajes_lexi(chat_id)), 2)

    def test_lexi_chat_rejects_invalid_messages_and_missing_chats(self):
        chat_id = database.crear_chat_lexi()

        with self.assertRaisesRegex(ValueError, "no puede estar vacío"):
            database.guardar_mensaje_lexi(chat_id, "user", "  ")
        with self.assertRaisesRegex(ValueError, "rol del mensaje"):
            database.guardar_mensaje_lexi(chat_id, "system", "texto")
        with self.assertRaisesRegex(LookupError, "No existe la conversación"):
            database.listar_mensajes_lexi(-1)
        with self.assertRaisesRegex(LookupError, "No existe la conversación"):
            database.guardar_mensaje_lexi(-1, "user", "consulta")

    def test_alert_days_use_latest_movement_date_not_insert_order(self):
        database.guardar_expediente({
            "expediente": "321/2026",
            "caratula": "Causa de prueba",
        }, desde_sae=True)
        for fecha, titulo in (
            ("2026-10-13 10:00:00", "Movimiento más reciente"),
            ("2026-10-10 10:00:00", "Movimiento anterior importado después"),
        ):
            database.guardar_novedad({
                "expediente": "321/2026",
                "fecha": fecha,
                "tipo": "Decreto",
                "titulo": titulo,
                "texto": titulo,
            })

        expediente = database.obtener_expediente("321/2026")
        alertas = database.alertas_por_inactividad(hoy=date(2026, 10, 14))

        self.assertEqual(expediente["ultimo"], "2026-10-13 10:00:00")
        self.assertEqual(alertas[0]["dias"], 1)

    def test_alert_days_read_latest_normalized_movement_instead_of_stale_last_field(self):
        database.guardar_expediente({
            "expediente": "654/2026",
            "caratula": "Causa importada",
            "ultimo": "01/01/2020",
        }, desde_sae=True)
        database.guardar_novedad({
            "expediente": "654/2026",
            "fecha": "2026-10-12 12:30:00",
            "tipo": "Decreto",
            "titulo": "Actuación reciente",
            "texto": "Actuación reciente",
        })
        database.guardar_expediente({
            "expediente": "654/2026",
            "caratula": "Causa importada",
            "ultimo": "01/01/2020",
        }, desde_sae=True)

        alertas = database.alertas_por_inactividad(hoy=date(2026, 10, 14))

        self.assertEqual(alertas[0]["dias"], 2)

    def test_personal_calendar_reminders_are_persisted_and_can_be_deleted(self):
        aviso = database.guardar_aviso_calendario(
            date(2026, 10, 20), "Presentar escrito", "14:30", "Acompañar copias."
        )
        eventos = database.novedades_para_calendario()
        guardado = next(evento for evento in eventos if evento.get("id") == aviso["id"])

        self.assertEqual(guardado["fecha"], date(2026, 10, 20))
        self.assertEqual(guardado["hora"], "14:30")
        self.assertEqual(guardado["caratula"], "Presentar escrito")
        self.assertEqual(guardado["diligencia"], "Acompañar copias.")
        self.assertTrue(guardado["es_aviso"])

        database.eliminar_aviso_calendario(aviso["id"])
        self.assertFalse(any(
            evento.get("id") == aviso["id"]
            for evento in database.novedades_para_calendario()
        ))

    def test_personal_calendar_reminder_rejects_invalid_values(self):
        with self.assertRaisesRegex(ValueError, "título"):
            database.guardar_aviso_calendario(date(2026, 10, 20), " ")
        with self.assertRaisesRegex(ValueError, "hora"):
            database.guardar_aviso_calendario(
                date(2026, 10, 20), "Presentar escrito", "25:90"
            )
        with self.assertRaisesRegex(ValueError, "fecha"):
            database.guardar_aviso_calendario(
                "20/10/2026", "Presentar escrito"
            )

    def test_ai_sources_are_local_and_findings_require_cited_calendar_confirmation(self):
        database.guardar_expediente({
            "expediente": "12392/21",
            "caratula": "Caso con actuación",
        }, desde_sae=True)
        database.guardar_novedad({
            "expediente": "12392/21",
            "fecha": "2026-05-01 10:00:00",
            "tipo": "Decreto",
            "titulo": "Audiencia",
            "texto": "Se fija audiencia para el 16/05/2026 a las 10:00.",
        })
        database.guardar_expediente({
            "expediente": "777/20",
            "caratula": "Otro caso",
        }, desde_sae=True)
        database.guardar_novedad({
            "expediente": "777/20",
            "fecha": "2026-05-02 10:00:00",
            "tipo": "Decreto",
            "titulo": "Otra actuación",
            "texto": "Se ordena una notificación.",
        })

        fuentes = database.buscar_fuentes_ia(
            "¿Qué dice el expediente 12392/21 sobre la audiencia?")
        self.assertEqual([fuente["expediente"] for fuente in fuentes], ["12392/21"])
        fuente = fuentes[0]
        reporte = database.guardar_analisis_ia(
            7,
            "Se fijó una audiencia, su fecha debe revisarse.",
            "qwen3:4b",
            fuentes,
            [{
                "source": {"id": fuente["id"]},
                "category": "fecha",
                "title": "Audiencia",
                "description": "Se menciona una fecha para audiencia.",
                "event_date": "2026-05-16",
                "date_text": "2026-05-16",
                "evidence_quote": "Se fija audiencia para el 16/05/2026",
                "certainty": "explicit",
                "confidence": 0.92,
            }],
        )

        hallazgo = database.listar_hallazgos_ia(estado="nueva")[0]
        self.assertEqual(hallazgo["fecha_detectada"], "2026-05-16")
        self.assertEqual(len(database.listar_analisis_ia()), 1)
        sugerencia = next(
            evento for evento in database.novedades_para_calendario()
            if evento.get("es_sugerencia_ia")
        )
        self.assertEqual(sugerencia["fecha"], date(2026, 5, 16))
        self.assertIn(hallazgo["cita"], sugerencia["diligencia"])

        aviso = database.agendar_hallazgo_ia(
            hallazgo["id"], "2026-05-17", "Audiencia revisada", "10:00",
            hallazgo["cita"],
        )
        duplicado = database.agendar_hallazgo_ia(
            hallazgo["id"], "2026-05-18", "No debe duplicarse")
        self.assertEqual(duplicado["id"], aviso["id"])
        self.assertEqual(duplicado["fecha"], date(2026, 5, 17))
        self.assertFalse(any(
            evento.get("es_sugerencia_ia")
            for evento in database.novedades_para_calendario()
        ))
        self.assertEqual(database.listar_hallazgos_ia(estado="agendada")[0]["aviso_id"],
                         aviso["id"])
        self.assertGreater(reporte, 0)

    def test_ai_all_latest_novelty_request_includes_latest_actuation_for_each_case(self):
        for numero in ("101/2026", "202/2026", "303/2026"):
            database.guardar_expediente({
                "expediente": numero,
                "caratula": f"Causa {numero}",
            }, desde_sae=True)
            database.guardar_novedad({
                "expediente": numero,
                "fecha": "2026-10-10 09:00:00",
                "tipo": "Decreto",
                "titulo": "Movimiento anterior",
                "texto": "Texto anterior que no debe aparecer.",
            })
            database.guardar_novedad({
                "expediente": numero,
                "fecha": "2026-10-14 09:00:00",
                "tipo": "Decreto",
                "titulo": f"Último movimiento de {numero}",
                "texto": f"Texto más reciente del expediente {numero}.",
            })

        fuentes = database.buscar_fuentes_ia(
            "Dame las últimas novedades de todos mis expedientes")

        self.assertEqual(
            {fuente["expediente"] for fuente in fuentes},
            {"101/2026", "202/2026", "303/2026"},
        )
        self.assertTrue(all("Texto más reciente" in fuente["texto"]
                            for fuente in fuentes))
        self.assertFalse(any("Texto anterior" in fuente["texto"]
                             for fuente in fuentes))

    def test_ai_chat_message_stores_and_loads_citations(self):
        chat_id = database.crear_chat_lexi()
        fuentes = [{
            "id": 9,
            "expediente": "12392/21",
            "fecha": "2026-05-01",
            "titulo": "Decreto",
        }]
        database.guardar_mensaje_lexi(
            chat_id, "assistant", "Cita respaldada [N9].", fuentes)

        mensaje = database.listar_mensajes_lexi(chat_id)[0]
        self.assertEqual(mensaje["fuentes"], fuentes)

    def test_ai_daily_summary_window_and_legacy_schema_migration(self):
        ruta_actual = database.DB_PATH
        ruta_legacy = Path(self.tempdir.name) / "legacy.sqlite3"
        with sqlite3.connect(ruta_legacy) as conexion:
            conexion.execute("""
                CREATE TABLE analisis_ia (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    periodo_dias INTEGER NOT NULL CHECK (periodo_dias IN (7, 30)),
                    resumen TEXT NOT NULL,
                    modelo TEXT NOT NULL,
                    cantidad_fuentes INTEGER NOT NULL DEFAULT 0,
                    creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conexion.execute("""
                INSERT INTO analisis_ia (periodo_dias, resumen, modelo)
                VALUES (7, 'Informe anterior', 'qwen3:4b')
            """)
        conexion.close()
        database.DB_PATH = ruta_legacy
        try:
            database.inicializar()
            self.assertEqual(database.listar_analisis_ia()[0]["resumen"],
                             "Informe anterior")

            database.guardar_expediente({
                "expediente": "55/2026",
                "caratula": "Audiencia nueva",
            }, desde_sae=True)
            database.guardar_novedad({
                "expediente": "55/2026",
                "fecha": "2026-10-14 09:00:00",
                "tipo": "Decreto",
                "titulo": "Audiencia",
                "texto": "Se fija audiencia para el 20/10/2026.",
            })
            self.assertEqual(len(database.listar_fuentes_para_resumen_ia(1)), 1)
            with database._conexion() as db:
                db.execute("""
                    INSERT INTO analisis_ia (periodo_dias, resumen, modelo)
                    VALUES (1, 'Informe diario', 'qwen3:4b')
                """)
                self.assertEqual(
                    db.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(database.listar_analisis_ia()[0]["periodo_dias"], 1)
        finally:
            database.DB_PATH = ruta_actual


if __name__ == "__main__":
    unittest.main()
