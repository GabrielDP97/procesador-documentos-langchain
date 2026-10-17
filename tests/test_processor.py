import base64
import errno
import unittest
from unittest.mock import Mock
from processor import (MAX_FILE_BYTES, TransientProcessingError, ValidationError,
                       analyze_document, process_batch, process_upload)


def upload(text="Ideas locales. Ideas útiles.\n\nOtro párrafo.", name="prueba.txt"):
    raw = text.encode("utf-8") if isinstance(text, str) else text
    return {"name": name, "content": base64.b64encode(raw).decode("ascii")}


class ProcessorTests(unittest.TestCase):
    def test_spanish_metrics(self):
        result = process_upload(upload())
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["statistics"]["paragraphs"], 2)
        self.assertEqual(result["statistics"]["words"], 6)
        self.assertEqual(result["keywords"][0], {"word": "ideas", "count": 2})
        self.assertEqual(result["preview"], "Ideas locales. Ideas útiles.")

    def test_transient_error_recovers(self):
        worker = Mock(side_effect=[TransientProcessingError(), analyze_document({"name": "prueba.txt", "bytes": 1, "text": "Hola"})])
        result = process_upload(upload(), worker=worker)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(worker.call_count, 2)

    def test_retries_stop_at_three(self):
        worker = Mock(side_effect=TransientProcessingError())
        result = process_upload(upload(), worker=worker)
        self.assertEqual(result["error_type"], "transient")
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(worker.call_count, 3)

    def test_os_busy_retries(self):
        worker = Mock(side_effect=OSError(errno.EBUSY, "busy"))
        self.assertEqual(process_upload(upload(), worker=worker)["attempts"], 3)

    def test_permanent_error_does_not_retry(self):
        worker = Mock(side_effect=PermissionError(errno.EACCES, "private detail"))
        result = process_upload(upload(), worker=worker)
        self.assertEqual(result["attempts"], 1)
        self.assertNotIn("private detail", result["error"])

    def test_bad_inputs_never_reach_processing(self):
        bad = [upload(name="a.pdf"), upload("  \n"), upload(b"\xff"), upload("hola\x00"),
               upload(name="../secreto.txt"), upload(b"a" * (MAX_FILE_BYTES + 1)),
               {"name": "a.txt", "content": "%%%"}, None]
        worker = Mock()
        for index, item in enumerate(bad):
            with self.subTest(index=index):
                result = process_upload(item, worker=worker, simulate_transient=True)
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["attempts"], 0)
        worker.assert_not_called()

    def test_mixed_batch(self):
        result = process_batch({"files": [upload(name="uno.md"), upload(name="dos.pdf"), upload(name="tres.txt")], "simulate_transient": True})
        self.assertEqual([r["name"] for r in result["results"]], ["uno.md", "dos.pdf", "tres.txt"])
        self.assertEqual([r["attempts"] for r in result["results"]], [2, 0, 2])
        self.assertEqual(result["summary"], {"total": 3, "ok": 2, "errors": 1})

    def test_utf8_bom_and_windows_lines(self):
        result = process_upload(upload(b"\xef\xbb\xbfTexto\r\n\r\nOtro"))
        self.assertEqual(result["statistics"]["lines"], 3)
        self.assertEqual(result["statistics"]["paragraphs"], 2)

    def test_batch_limits(self):
        for payload in [None, {"files": []}, {"files": [upload()] * 11}, {"files": [upload()], "simulate_transient": "yes"}]:
            with self.assertRaises(ValidationError):
                process_batch(payload)


if __name__ == "__main__":
    unittest.main()
