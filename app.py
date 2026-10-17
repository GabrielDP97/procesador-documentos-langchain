"""Servidor local, sin persistencia de documentos ni servicios externos."""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from processor import ValidationError, process_batch

STATIC = Path(__file__).parent / "web"
MAX_REQUEST_BYTES = 14 * 1024 * 1024
PROCESSING_SLOTS = threading.BoundedSemaphore(2)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, format, *args):
        # No registrar nombres, documentos ni cuerpos de las peticiones.
        pass

    def send_content(self, status, content, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)

    def reply(self, status, value):
        self.send_content(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def local_request(self):
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        return self.headers.get("Host") in allowed

    def do_GET(self):
        if not self.local_request():
            return self.reply(403, {"error": "Acceso local requerido."})
        if self.path == "/api/health":
            return self.reply(200, {"status": "ok"})
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/style.css": ("style.css", "text/css; charset=utf-8")}
        if self.path not in assets:
            return self.reply(404, {"error": "Página no encontrada."})
        name, content_type = assets[self.path]
        self.send_content(200, (STATIC / name).read_bytes(), content_type)

    def do_POST(self):
        port = self.server.server_port
        origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        if not self.local_request() or self.headers.get("Origin") not in origins:
            return self.reply(403, {"error": "Abre la aplicación desde su dirección local."})
        if self.path != "/api/process":
            return self.reply(404, {"error": "Ruta no encontrada."})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.reply(415, {"error": "Se esperaba una petición JSON."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if not 0 < size <= MAX_REQUEST_BYTES:
            self.close_connection = True
            return self.reply(413, {"error": "El lote supera el tamaño permitido o está vacío."})
        if not PROCESSING_SLOTS.acquire(blocking=False):
            return self.reply(429, {"error": "Hay otros documentos procesándose. Vuelve a intentarlo en unos segundos."})
        try:
            payload = json.loads(self.rfile.read(size))
            result = process_batch(payload)
            self.reply(200, result)
        except ValidationError as exc:
            self.reply(400, {"error": str(exc)})
        except (ValueError, UnicodeDecodeError):
            self.reply(400, {"error": "La petición no contiene un JSON válido o el lote no es válido."})
        except Exception:
            self.reply(500, {"error": "No se pudo completar el lote. Vuelve a intentarlo."})
        finally:
            PROCESSING_SLOTS.release()


def main():
    parser = argparse.ArgumentParser(description="Procesador local de documentos")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with LocalServer(("127.0.0.1", args.port), Handler) as server:
        print(f"Aplicación disponible en http://127.0.0.1:{server.server_port}", flush=True)
        print("Pulsa Ctrl+C para cerrar. Los documentos solo se mantienen en memoria.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
