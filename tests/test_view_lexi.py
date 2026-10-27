import unittest

from view_lexi import _contenido_visible


class LexiMessageDisplayTests(unittest.TestCase):
    def test_legacy_source_footer_and_raw_citation_markers_are_hidden(self):
        contenido = (
            "Respuesta sobre la audiencia [N981].\n\n"
            "Fuentes consultadas: [N981] Exp. 4700/09 · 01/05/2026\n"
            "Las fechas identificadas son sugerencias, no vencimientos "
            "confirmados. Revisa la fuente original."
        )

        visible = _contenido_visible(contenido)

        self.assertEqual(visible, "Respuesta sobre la audiencia.")
        self.assertNotIn("[N981]", visible)
        self.assertNotIn("Fuentes consultadas", visible)
        self.assertNotIn("vencimientos confirmados", visible)

    def test_legacy_summary_hides_citation_line_without_dropping_summary(self):
        contenido = (
            "Resumen de novedades\n\nAudiencia próxima.\n\n"
            "Cita: Se fija audiencia [N123]"
        )

        self.assertEqual(
            _contenido_visible(contenido),
            "Resumen de novedades\n\nAudiencia próxima.",
        )


if __name__ == "__main__":
    unittest.main()
