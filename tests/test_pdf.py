import json
import unittest
from unittest.mock import patch

from pdf_fixtures import make_pdf
from test_processor import upload
from processor import process_batch, process_upload


class PdfTests(unittest.TestCase):
    def test_extracts_all_pages_and_spanish_characters(self):
        raw = make_pdf(["Ideas útiles en español.", "Más ideas para mañana."])
        result = process_upload(upload(raw, "informe.PDF"))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["statistics"]["words"], 8)
        self.assertIn("español", result["preview"])
        self.assertIn({"word": "mañana", "count": 1}, result["keywords"])
        self.assertEqual(result["source"], {"format": "pdf", "pages": 2, "pages_without_text": []})
        self.assertEqual(result["bytes"], len(raw))
        self.assertEqual(result["warnings"], [])

    def test_image_only_pdf_requests_ocr_without_retry(self):
        result = process_upload(upload(make_pdf([None]), "escaneo.pdf"), simulate_transient=True)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["attempts"], 0)
        self.assertIn("OCR", result["error"])

    def test_mixed_pages_warns_about_missing_text(self):
        result = process_upload(upload(make_pdf(["Texto disponible.", None, "Otra página."]), "mixto.pdf"))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source"]["pages_without_text"], [2])
        self.assertIn("2", result["warnings"][0])
        self.assertIn("OCR", result["warnings"][0])

    def test_protected_pdf_is_rejected_without_retry(self):
        result = process_upload(upload(make_pdf(password="solo-pruebas"), "protegido.pdf"))
        self.assertEqual(result["attempts"], 0)
        self.assertIn("contraseña", result["error"])

    def test_damaged_pdf_and_fake_extension(self):
        for raw in [b"%PDF-1.7\narchivo roto\n%%EOF", b"esto no es un PDF"]:
            with self.subTest(raw=raw):
                result = process_upload(upload(raw, "roto.pdf"))
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["error_type"], "validation")
                self.assertEqual(result["attempts"], 0)

    def test_page_and_extraction_limits(self):
        for raw in [make_pdf([]), make_pdf(["Texto"] * 101)]:
            result = process_upload(upload(raw, "paginas.pdf"))
            self.assertEqual(result["attempts"], 0)
            self.assertIn("100 páginas", result["error"])
        raw = make_pdf()
        with patch("processor.MAX_PDF_TEXT_CHARACTERS", 2):
            self.assertIn("demasiado texto", process_upload(upload(raw, "largo.pdf"))["error"])
        with patch("processor.MAX_PDF_STREAM_BYTES", 2):
            self.assertIn("complejo", process_upload(upload(raw, "complejo.pdf"))["error"])

    def test_batch_and_json_preserve_pdf_metadata(self):
        report = process_batch({"files": [upload(make_pdf(), "informe.pdf"), upload(name="nota.txt"),
                                          upload(make_pdf([None]), "escaneo.pdf")], "simulate_transient": True})
        exported = json.loads(json.dumps(report, ensure_ascii=False))
        self.assertEqual(exported["summary"], {"total": 3, "ok": 2, "errors": 1})
        self.assertEqual([r["attempts"] for r in exported["results"]], [2, 2, 0])
        self.assertEqual(exported["results"][0]["source"]["pages"], 1)


if __name__ == "__main__":
    unittest.main()
