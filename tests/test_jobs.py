import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from app import Handler, LocalServer
from jobs import Jobs
from processor import ValidationError
from pdf_fixtures import make_pdf


class JobTests(unittest.TestCase):
    def setUp(self):
        self.server = LocalServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, body=None, **extra):
        headers = {"Origin": f"http://127.0.0.1:{self.port}", "Content-Type": "application/octet-stream", **extra}
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            c.request(method, path, body, headers)
            r = c.getresponse()
            return r.status, json.loads(r.read())
        finally:
            c.close()

    def finish(self, token):
        for _ in range(200):
            status, data = self.request("GET", "/api/jobs/" + token)
            self.assertEqual(status, 200)
            if data["status"] in {"done", "cancelled"}:
                return data
            time.sleep(.02)
        self.fail("El trabajo no terminó")

    def test_large_binary_pdf_and_cleanup(self):
        from pypdf import PdfReader, PdfWriter
        from io import BytesIO
        writer = PdfWriter()
        writer.append(PdfReader(BytesIO(make_pdf())))
        writer.add_metadata({"/TestPadding": "x" * (2 * 1024 * 1024)})
        output = BytesIO()
        writer.write(output)
        raw = output.getvalue()
        status, data = self.request("POST", "/api/jobs", raw, **{"X-File-Name": "grande.pdf"})
        self.assertEqual(status, 202)
        result = self.finish(data["id"])
        self.assertEqual(result["result"]["status"], "ok", result)
        self.assertEqual(result["result"]["bytes"], len(raw))
        self.assertFalse(self.server.jobs.items[data["id"]]["path"].exists())
        self.assertEqual(self.request("GET", "/api/health")[0], 200)

    def test_cancel_queued_job_and_cleanup(self):
        self.server.jobs.worker.acquire()
        try:
            status, data = self.request("POST", "/api/jobs", b"Hola mundo", **{"X-File-Name": "nota.txt"})
            self.assertEqual(status, 202)
            self.assertEqual(self.request("POST", "/api/jobs/" + data["id"] + "/cancel", b"")[0], 200)
            result = self.finish(data["id"])
            self.assertEqual(result["status"], "cancelled")
            self.assertFalse(self.server.jobs.items[data["id"]]["path"].exists())
        finally:
            self.server.jobs.worker.release()

    def test_reject_invalid_names_languages_and_limits(self):
        for header in [{"X-File-Name": "..%2Fnota.txt"}, {"X-File-Name": "a.txt", "X-OCR-Languages": "invalid"},
                       {"X-File-Name": "a.pdf", "Content-Length": str(150 * 1024 * 1024 + 1)}]:
            self.assertEqual(self.request("POST", "/api/jobs", b"", **header)[0], 400)
        self.assertEqual(self.request("GET", "/api/jobs/missing")[0], 404)

    def test_queue_bounded_and_abandoned_upload_removed(self):
        jobs = Jobs()
        a = jobs.reserve("a.txt", "spa+eng", 1)
        b = jobs.reserve("b.txt", "spa+eng", 1)
        self.assertIsNone(jobs.reserve("c.txt", "spa+eng", 1))
        jobs.abandon(a)
        self.assertFalse(a["path"].exists())
        c = jobs.reserve("c.txt", "spa+eng", 1)
        jobs.abandon(b)
        jobs.abandon(c)

    def test_selected_language_passed_to_pdf(self):
        from processor import process_file
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scan.pdf"
            path.write_bytes(make_pdf([None]))
            with patch("processor.recognize_pdf_pages", return_value=({1: "Deutsches Dokument"}, {})) as ocr:
                result = process_file(path, "scan.pdf", languages="deu+eng")
            self.assertEqual(result["source"]["ocr_languages"], ["deu", "eng"])
            self.assertEqual(ocr.call_args.kwargs["languages"], "deu+eng")

    def test_interrupted_upload_releases_slot_and_tempfile(self):
        import socket
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.putrequest("POST", "/api/jobs")
        c.putheader("Origin", f"http://127.0.0.1:{self.port}")
        c.putheader("Content-Type", "application/octet-stream")
        c.putheader("X-File-Name", "parcial.pdf")
        c.putheader("Content-Length", "1000")
        c.endheaders()
        c.send(b"%PDF-")
        c.sock.shutdown(socket.SHUT_WR)
        response = c.getresponse()
        self.assertEqual(response.status, 400)
        response.read()
        c.close()
        for _ in range(50):
            if not self.server.jobs.items:
                break
            time.sleep(.02)
        self.assertEqual(self.server.jobs.items, {})

    def test_job_upload_requires_local_origin(self):
        self.assertEqual(self.request("POST", "/api/jobs", b"Hi", **{"Origin": "https://evil.example", "X-File-Name": "a.txt"})[0], 403)
