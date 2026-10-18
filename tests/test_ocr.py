import subprocess
import unittest
from io import BytesIO
from unittest.mock import patch

from pypdf import PdfReader
from pdf_fixtures import make_pdf, make_scanned_pdf
from test_processor import upload
from processor import process_upload
from ocr import OcrError, recognize_pdf_pages, tesseract_command


class OcrTests(unittest.TestCase):
    def test_digital_pdf_does_not_call_ocr(self):
        with patch("processor.recognize_pdf_pages") as recognize:
            self.assertEqual(process_upload(upload(make_pdf(), "digital.pdf"))["status"], "ok")
            recognize.assert_not_called()

    def test_ocr_combines_pages_in_original_order(self):
        with patch("processor.recognize_pdf_pages", return_value=({1: "Primera página reconocida.", 3: "Última página reconocida."}, {})) as recognize:
            result = process_upload(upload(make_pdf([None, "Texto digital intermedio.", None]), "mixto.pdf"))
        self.assertEqual(recognize.call_args.args[1], [1, 3])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source"]["ocr_pages"], [1, 3])
        self.assertEqual(result["source"]["pages_without_text"], [])
        self.assertEqual(result["preview"], "Primera página reconocida.")
        self.assertEqual(result["statistics"]["paragraphs"], 3)
        self.assertIn("puede contener errores", result["warnings"][0])

    def test_missing_ocr_preserves_digital_text(self):
        with patch("processor.recognize_pdf_pages", side_effect=OcrError("Instala Tesseract.")):
            result = process_upload(upload(make_pdf(["Texto válido", None]), "mixto.pdf"))
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["source"]["pages_without_text"], [2])
            self.assertIn("Instala Tesseract", " ".join(result["warnings"]))
            result = process_upload(upload(make_pdf([None]), "escaneo.pdf"))
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["attempts"], 0)
            self.assertIn("Instala Tesseract", result["error"])

    def test_ocr_page_limit(self):
        with self.assertRaisesRegex(OcrError, "1000 páginas"):
            recognize_pdf_pages(b"", list(range(1, 1002)))

    def test_timeout_is_reported(self):
        with patch("ocr.tesseract_command", return_value="tesseract"), patch("ocr.render_page", return_value=b"png"), patch("ocr.subprocess.run", side_effect=subprocess.TimeoutExpired("tesseract", 20)):
            texts, issues = recognize_pdf_pages(b"", [1])
        self.assertEqual(texts, {})
        self.assertIn("tiempo", issues[1])

    def test_real_scanned_document_end_to_end(self):
        try:
            tesseract_command()
        except OcrError as exc:
            self.skipTest(str(exc))
        raw = make_scanned_pdf()
        reader = PdfReader(BytesIO(raw))
        self.assertFalse(reader.pages[0].extract_text().strip())
        result = process_upload(upload(raw, "escaneado.pdf"))
        self.assertEqual(result["status"], "ok", result.get("error"))
        self.assertEqual(result["source"]["ocr_pages"], [1])
        self.assertGreater(result["statistics"]["words"], 15)
        self.assertIn("proyectos", str(result["keywords"]) + result["preview"])


if __name__ == "__main__":
    unittest.main()
