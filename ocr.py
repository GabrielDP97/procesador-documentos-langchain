"""OCR local: PDFium renderiza en memoria y Tesseract reconoce por stdin/stdout."""
import math
import os
import shutil
import subprocess
import threading
import time
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium

MAX_OCR_PAGES = 1000
MAX_RENDER_PIXELS = 8_000_000
OCR_PAGE_TIMEOUT = 20
OCR_DOCUMENT_TIMEOUT = 7200
# PDFium no admite llamadas simultáneas, ni siquiera para documentos distintos.
PDFIUM_LOCK = threading.Lock()


class OcrError(Exception):
    pass


@lru_cache(maxsize=4)
def tesseract_command(requested="spa+eng"):
    command = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract")
    if not command and os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Tesseract-OCR/tesseract.exe"
        if candidate.is_file():
            command = str(candidate)
    if not command:
        raise OcrError("Instala Tesseract con los idiomas español (spa) e inglés (eng) y reinicia la aplicación.")
    try:
        result = subprocess.run([command, "--list-langs"], capture_output=True, timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OcrError("No se pudo iniciar Tesseract. Revisa su instalación y reinicia la aplicación.") from exc
    languages = set(result.stdout.decode("utf-8", errors="replace").splitlines())
    if result.returncode or not set(requested.split("+")) <= languages:
        raise OcrError("Tesseract necesita los idiomas seleccionados. Instálalos y reinicia la aplicación.")
    return command


def render_page(raw, index):
    with PDFIUM_LOCK:
        with pdfium.PdfDocument(str(raw) if isinstance(raw, Path) else raw) as document:
            page = document[index]
            try:
                width, height = page.get_size()
                if not math.isfinite(width * height) or width <= 0 or height <= 0:
                    raise OcrError("La página tiene dimensiones no válidas.")
                scale = min(200 / 72, math.sqrt(MAX_RENDER_PIXELS / (width * height)))
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    try:
                        with BytesIO() as stream:
                            image.save(stream, format="PNG")
                            return stream.getvalue()
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()


def recognize_pdf_pages(raw, numbers, *, progress=None, cancel=None, languages="spa+eng"):
    if len(numbers) > MAX_OCR_PAGES:
        raise OcrError(f"El documento necesita OCR en más de {MAX_OCR_PAGES} páginas.")
    command = tesseract_command(languages)
    deadline = time.monotonic() + OCR_DOCUMENT_TIMEOUT
    texts, issues = {}, {}
    for done, number in enumerate(numbers, start=1):
        if cancel and cancel.is_set():
            raise OcrError("Procesamiento cancelado.")
        if progress:
            progress("OCR", done - 1, len(numbers))
        if time.monotonic() >= deadline:
            issues[number] = "Se ha alcanzado el límite de 7200 segundos de OCR por documento."
            continue
        try:
            png = render_page(raw, number - 1)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OcrError("Se ha alcanzado el límite de tiempo de OCR.")
            result = subprocess.run(
                [command, "stdin", "stdout", "-l", languages, "--psm", "3"], input=png,
                capture_output=True, timeout=min(OCR_PAGE_TIMEOUT, remaining),
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if result.returncode:
                raise OcrError("Tesseract no ha podido reconocer esta página.")
            texts[number] = result.stdout.decode("utf-8", errors="replace").strip()
        except subprocess.TimeoutExpired:
            issues[number] = "El reconocimiento de esta página ha superado el tiempo permitido."
        except OcrError as exc:
            issues[number] = str(exc)
        except Exception:
            issues[number] = "No se ha podido aplicar OCR a esta página."
    return texts, issues
