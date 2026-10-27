import json
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from ai_service import AIServiceError, OllamaService, _preparar_fuentes


class OllamaServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = OllamaService()
        self.source = {
            "id": 17,
            "hash": "hash-local",
            "expediente": "12392/21",
            "caratula": "Caso de prueba",
            "fecha": "2026-05-01",
            "titulo": "Decreto",
            "texto": "Se fija audiencia para el 2026-05-16 a las 10:00.",
        }

    def test_service_rejects_non_local_ollama_hosts(self):
        with self.assertRaisesRegex(ValueError, "localhost"):
            OllamaService(base_url="https://example.com")

    def test_answer_only_returns_citations_from_retrieved_sources(self):
        result_content = json.dumps({
            "message": "",
            "cases": [{
                "source_id": 17,
                "que_paso": "Se fijó audiencia para el 16 de mayo.",
                "accion_requerida": "Controlar la comparecencia.",
            }],
            "schedule": None,
        })
        with patch.object(self.service, "comprobar_disponibilidad"):
            with patch.object(
                self.service, "_request_json",
                return_value={"message": {"content": result_content}},
            ):
                response = self.service.responder(
                    "¿Cuándo es la audiencia?", [self.source])

        self.assertEqual(response["sources"][0]["id"], 17)
        self.assertEqual(len(response["sources"]), 1)
        self.assertIn("📌 **Expediente: 12392/21**", response["answer"])
        self.assertIn("• **¿Qué pasó?**:", response["answer"])
        self.assertIn("• **Fecha**: 01/05/2026", response["answer"])
        self.assertIn(
            "• **Acción requerida / Plazo**: Controlar la comparecencia.",
            response["answer"],
        )
        self.assertNotIn("[N17]", response["answer"])
        self.assertNotIn("Fuentes consultadas", response["answer"])

    def test_prompt_is_strict_and_source_text_is_sanitized_before_local_model(self):
        fuente = {
            **self.source,
            "texto": (
                "PODER JUDICIAL DE TUCUMÁN\nCENTRO JUDICIAL CAPITAL\n"
                "Se fija audiencia para 2026-05-16. [N980]\n"
                "Certificado digital: CN=JUEZ, SERIALNUMBER=123456, "
                "CUIL: 20123456789\nActuación firmada en fecha 2026-05-01"
            ),
        }
        content = json.dumps({
            "message": "",
            "cases": [{
                "source_id": 17,
                "que_paso": "Se fijó una audiencia [N17].",
                "accion_requerida": "Mero trámite / Informativo.",
            }],
            "schedule": None,
        })
        with patch.object(self.service, "comprobar_disponibilidad"):
            with patch.object(
                self.service, "_request_json",
                return_value={"message": {"content": content}},
            ) as request:
                respuesta = self.service.responder("Resume la actuación", [fuente])

        payload = request.call_args.args[2]
        system_prompt = payload["messages"][0]["content"]
        user_prompt = payload["messages"][1]["content"]
        self.assertIn("100% en español neutral/argentino", system_prompt)
        self.assertIn("NO agregues disclaimers", system_prompt)
        self.assertIn("Acción requerida / Plazo", system_prompt)
        self.assertNotIn("PODER JUDICIAL", user_prompt)
        self.assertNotIn("CENTRO JUDICIAL", user_prompt)
        self.assertNotIn("SERIALNUMBER", user_prompt)
        self.assertNotIn("CUIL", user_prompt)
        self.assertNotIn("[N980]", user_prompt)
        self.assertNotIn("[N17]", respuesta["answer"])
        self.assertNotIn("CN=", respuesta["answer"])
        self.assertNotIn("SERIALNUMBER", respuesta["answer"])
        self.assertNotIn("CUIL", respuesta["answer"])

    def test_input_sanitizer_removes_signatures_and_repetitive_headers(self):
        fuentes = _preparar_fuentes([{
            **self.source,
            "texto": (
                "PODER JUDICIAL DE TUCUMÁN\nCENTRO JUDICIAL CAPITAL\n"
                "Actuación firmada en fecha 2026-05-01\n"
                "Certificado digital: CN=JUEZ, SERIALNUMBER=12345, "
                "CUIL: 20123456789\n[N980]\nSe corre traslado."
            ),
        }], 8)

        texto = fuentes[0]["texto"]
        for token in (
            "PODER JUDICIAL", "CENTRO JUDICIAL", "firmada",
            "Certificado digital", "CN=", "SERIALNUMBER", "CUIL", "[N980]",
        ):
            self.assertNotIn(token.casefold(), texto.casefold())
        self.assertIn("Se corre traslado.", texto)

    def test_summary_drops_findings_without_a_verifiable_literal_quote(self):
        content = json.dumps({
            "overview": "La actuación fija una audiencia.",
            "findings": [
                {
                    "source_id": 17,
                    "category": "fecha",
                    "title": "Audiencia",
                    "description": "Se menciona una fecha explícita.",
                    "event_date": "2026-05-16",
                    "date_text": "2026-05-16",
                    "evidence_quote": "Se fija audiencia para el 2026-05-16",
                    "certainty": "explicit",
                    "confidence": 0.95,
                },
                {
                    "source_id": 17,
                    "category": "fecha",
                    "title": "Fecha inventada",
                    "description": "No aparece en la actuación.",
                    "event_date": "2026-05-20",
                    "date_text": "2026-05-20",
                    "evidence_quote": "Se celebrará la audiencia el 2026-05-20",
                    "certainty": "explicit",
                    "confidence": 0.8,
                },
            ],
        })
        with patch.object(self.service, "comprobar_disponibilidad"):
            with patch.object(
                self.service, "_request_json",
                return_value={"message": {"content": content}},
            ):
                response = self.service.resumir_novedades([self.source], 7)

        self.assertEqual(len(response["findings"]), 1)
        finding = response["findings"][0]
        self.assertEqual(finding["event_date"], "2026-05-16")
        self.assertTrue(finding["requires_review"])
        self.assertEqual(finding["source"]["id"], 17)

    def test_summary_surfaces_contextual_literal_dates_for_human_review(self):
        fuente = {
            **self.source,
            "texto": (
                "Se fija una audiencia ficticia para el día 18/05/2026 "
                "a las 10:30."
            ),
        }
        content = json.dumps({
            "overview": "La actuación menciona una audiencia.",
            "findings": [],
        })
        with patch.object(self.service, "comprobar_disponibilidad"):
            with patch.object(
                self.service, "_request_json",
                return_value={"message": {"content": content}},
            ):
                response = self.service.resumir_novedades([fuente], 7)

        self.assertEqual(len(response["findings"]), 1)
        finding = response["findings"][0]
        self.assertEqual(finding["event_date"], "2026-05-18")
        self.assertEqual(finding["date_text"], "18/05/2026")
        self.assertTrue(finding["requires_review"])

    def test_empty_sources_produce_an_evidence_limited_answer_without_network(self):
        with patch.object(self.service, "_request_json") as request:
            response = self.service.responder("¿Qué ocurrió?", [])

        request.assert_not_called()
        self.assertEqual(response["sources"], [])
        self.assertEqual(
            response["answer"],
            "No encontré actuaciones guardadas con texto para responder esa consulta.",
        )

    def test_general_latest_news_query_includes_every_source_in_several_batches(self):
        fuentes = [
            {
                **self.source,
                "id": source_id,
                "expediente": f"{source_id}/2026",
                "titulo": "Audiencia" if source_id == 17 else "Decreto",
                "texto": (
                    "Se fija audiencia para el 18 de mayo."
                    if source_id == 17 else
                    f"Se ordena una medida procesal para la causa {source_id}."
                ),
            }
            for source_id in range(17, 24)
        ]

        def respuesta_por_lote(_method, _path, payload):
            user_prompt = payload["messages"][1]["content"]
            contexto = user_prompt.split(
                "Evidencia local autorizada (source_id es interno):\n", 1
            )[1].split("\n\nPregunta del abogado:", 1)[0]
            lote_ids = [fuente["id"] for fuente in json.loads(contexto)]
            return {"message": {"content": json.dumps({
                "message": "",
                "cases": [
                    {
                        "source_id": source_id,
                        "que_paso": (
                            "Audiencia"
                            if source_id == 17 else
                            f"Se ordenó una medida en la causa {source_id}."
                        ),
                        "accion_requerida": "Mero trámite / Informativo",
                    }
                    for source_id in lote_ids
                ],
                "schedule": None,
            })}}

        with patch.object(self.service, "comprobar_disponibilidad"):
            with patch.object(
                self.service, "_request_json", side_effect=respuesta_por_lote,
            ) as request:
                respuesta = self.service.responder(
                    "Dame las últimas novedades de todos mis expedientes.",
                    fuentes,
                )

        self.assertEqual(request.call_count, 3)
        for fuente in fuentes:
            self.assertIn(f"**Expediente: {fuente['expediente']}**",
                          respuesta["answer"])
        self.assertIn("Se fija audiencia para el 18 de mayo",
                      respuesta["answer"])
        self.assertNotIn("**¿Qué pasó?**: Audiencia", respuesta["answer"])
        self.assertEqual(len(respuesta["sources"]), len(fuentes))

    def test_explicit_scheduling_request_returns_only_a_date_time_matching_event(self):
        fecha_evento = date.today() + timedelta(days=2)
        pregunta = (
            "Agéndame una reunión el "
            f"{fecha_evento.strftime('%d/%m/%Y')} a las 14:30 "
            "para revisar el expediente."
        )
        content = json.dumps({
            "message": "",
            "cases": [],
            "schedule": {
                "title": "Revisión del expediente",
                "date": fecha_evento.isoformat(),
                "time": "14:30",
                "details": "Revisar el expediente.",
            },
        })
        with patch.object(self.service, "comprobar_disponibilidad"):
            with patch.object(
                self.service, "_request_json",
                return_value={"message": {"content": content}},
            ):
                respuesta = self.service.responder(pregunta, [])

        self.assertEqual(respuesta["scheduled_event"]["date"], fecha_evento)
        self.assertEqual(respuesta["scheduled_event"]["time"], "14:30")
        self.assertIn("Agendado en el calendario", respuesta["answer"])

    def test_schedule_request_without_explicit_time_does_not_create_event(self):
        fecha_evento = date.today() + timedelta(days=2)
        content = json.dumps({
            "message": "",
            "cases": [],
            "schedule": None,
        })
        with patch.object(self.service, "comprobar_disponibilidad"):
            with patch.object(
                self.service, "_request_json",
                return_value={"message": {"content": content}},
            ):
                respuesta = self.service.responder(
                    f"Agéndame una reunión el {fecha_evento.isoformat()}.", [])

        self.assertIsNone(respuesta["scheduled_event"])
        self.assertIn("necesito que indiques", respuesta["answer"])

    def test_a_date_mentioned_without_schedule_intent_never_creates_event(self):
        fecha_evento = date.today() + timedelta(days=2)
        content = json.dumps({
            "message": "",
            "cases": [{
                "source_id": 17,
                "que_paso": "Se fijó una audiencia.",
                "accion_requerida": "Controlar la comparecencia.",
            }],
            "schedule": {
                "title": "Audiencia",
                "date": fecha_evento.isoformat(),
                "time": "14:30",
                "details": "",
            },
        })
        with patch.object(self.service, "comprobar_disponibilidad"):
            with patch.object(
                self.service, "_request_json",
                return_value={"message": {"content": content}},
            ):
                respuesta = self.service.responder(
                    f"¿Qué audiencia tengo el {fecha_evento.isoformat()} "
                    "a las 14:30?", [self.source])

        self.assertIsNone(respuesta["scheduled_event"])

    def test_invalid_structured_model_output_is_reported(self):
        with patch.object(self.service, "comprobar_disponibilidad"):
            with patch.object(
                self.service, "_request_json",
                return_value={"message": {"content": "No es JSON"}},
            ):
                with self.assertRaises(AIServiceError):
                    self.service.responder("¿Qué ocurrió?", [self.source])


if __name__ == "__main__":
    unittest.main()
