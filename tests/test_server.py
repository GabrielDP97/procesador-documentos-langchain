import base64
import http.client
import json
import threading
import unittest
from app import Handler, LocalServer, MAX_REQUEST_BYTES


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port
        cls.origin = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body, headers or {})
            response = conn.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            conn.close()

    def test_page_and_api(self):
        status, body, headers = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b'lang="es"', body)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        payload = {"files": [{"name": "hola.txt", "content": base64.b64encode(b"Hola, mundo.").decode()}]}
        status, body, _ = self.request("POST", "/api/process", json.dumps(payload), {"Content-Type": "application/json", "Origin": self.origin})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["summary"]["ok"], 1)
        self.assertEqual(result["results"][0]["statistics"]["words"], 2)

    def test_no_filesystem_access(self):
        self.assertEqual(self.request("GET", "/../processor.py")[0], 404)
        self.assertEqual(self.request("GET", "/processor.py")[0], 404)

    def test_external_origins_and_hosts_blocked(self):
        self.assertEqual(self.request("GET", "/", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/process", "{}", {"Content-Type": "application/json", "Origin": "https://evil.example"})[0], 403)

    def test_bad_and_oversized_requests(self):
        headers = {"Content-Type": "application/json", "Origin": self.origin}
        self.assertEqual(self.request("POST", "/api/process", "{", headers)[0], 400)
        headers["Content-Length"] = str(MAX_REQUEST_BYTES + 1)
        self.assertEqual(self.request("POST", "/api/process", "", headers)[0], 413)


if __name__ == "__main__":
    unittest.main()
