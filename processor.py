"""Procesamiento determinista en memoria mediante LangChain Core."""
import base64
import binascii
import errno
import os
import re
import unicodedata
from collections import Counter
from io import BytesIO
from pathlib import PurePath
from pypdf import PdfReader
from ocr import OcrError, recognize_pdf_pages

# Este proyecto no envía trazas ni documentos a servicios externos.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.pop("LANGCHAIN_TRACING", None)
from langchain_core.runnables import RunnableLambda

MAX_FILE_BYTES = 1024 * 1024
MAX_FILES = 10
MAX_ATTEMPTS = 3
MAX_PDF_PAGES = 100
MAX_PDF_STREAM_BYTES = 5 * 1024 * 1024
MAX_PDF_TEXT_CHARACTERS = 1_000_000
STOP_WORDS = set("""a al algo ante aquel aquí así aunque bajo cada como con contra cual
cuando de del desde donde dos el ella ellas ellos en entre era es esa esas ese esos
esta estaba estas este esto estos fue ha hasta hay la las le les lo los más me mi
mientras muy ni no nos o otra otro para pero por porque que qué quien se ser si sin
sobre son su sus también te tiene todo tras tu un una unas uno unos ya y the and of
to in is it for on with as at be by from that this are was were an or not you your""".split())


class ValidationError(ValueError):
    """Error de entrada que no mejora al reintentarlo."""


class TransientProcessingError(Exception):
    """Operación temporalmente no disponible."""


def extract_pdf(raw):
    """Extrae texto de todas las páginas, sin ejecutar contenido del PDF."""
    if not raw.lstrip().startswith(b"%PDF-"):
        raise ValidationError("El archivo no contiene un PDF válido. No basta con cambiar su extensión.")
    try:
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            raise ValidationError("El PDF está protegido. Guarda una copia sin contraseña para procesarlo.")
        page_count = len(reader.pages)
        if not 1 <= page_count <= MAX_PDF_PAGES:
            raise ValidationError("El PDF debe tener entre 1 y 100 páginas.")
        texts, empty_pages = {}, []
        text_size = 0
        stream_size = 0
        for number, page in enumerate(reader.pages, start=1):
            contents = page.get_contents()
            stream_size += len(contents.get_data()) if contents is not None else 0
            if stream_size > MAX_PDF_STREAM_BYTES:
                raise ValidationError("El contenido del PDF es demasiado complejo. Divídelo en documentos más pequeños.")
            text = (page.extract_text() or "").strip()
            # Algunos PDF incluyen separadores de página como caracteres de control.
            text = "".join(c for c in text if unicodedata.category(c) != "Cc" or c in "\n\r\t")
            if text.strip():
                text_size += len(text)
                if text_size > MAX_PDF_TEXT_CHARACTERS:
                    raise ValidationError("El PDF contiene demasiado texto. Divídelo en documentos más pequeños.")
                texts[number] = text
            else:
                empty_pages.append(number)
        warnings = []
        ocr_pages, attempted_pages = [], []
        ocr_issue = None
        if empty_pages:
            try:
                recognized, issues = recognize_pdf_pages(raw, empty_pages)
                attempted_pages = list(empty_pages)
                for number in empty_pages:
                    text = recognized.get(number, "").strip()
                    text = "".join(c for c in text if unicodedata.category(c) != "Cc" or c in "\n\r\t")
                    if text.strip():
                        text_size += len(text)
                        if text_size > MAX_PDF_TEXT_CHARACTERS:
                            raise ValidationError("El PDF contiene demasiado texto. Divídelo en documentos más pequeños.")
                        texts[number] = text
                        ocr_pages.append(number)
                    if number in issues:
                        warnings.append(f"OCR, página {number}: {issues[number]}")
                if issues:
                    ocr_issue = next(iter(issues.values()))
            except OcrError as exc:
                ocr_issue = str(exc)
                warnings.append(f"OCR no disponible para este documento: {ocr_issue}")
        if not texts:
            if ocr_issue:
                raise ValidationError(f"No se pudo obtener texto mediante OCR: {ocr_issue}")
            raise ValidationError("El OCR no ha reconocido texto. Comprueba que el escaneo sea legible y esté orientado correctamente; la página también puede estar en blanco.")
        if ocr_pages:
            warnings.insert(0, "OCR aplicado en las páginas " + ", ".join(map(str, ocr_pages)) + ". Revisa el texto reconocido: puede contener errores.")
        empty_pages = [number for number in empty_pages if number not in texts]
        if empty_pages:
            pages = ", ".join(str(number) for number in empty_pages)
            warnings.append(f"Páginas sin texto reconocido: {pages}. Pueden estar en blanco o tener imágenes ilegibles. El análisis incluye solo las páginas con texto; revisa el resultado del OCR.")
        return {"text": "\n\n".join(texts[number] for number in sorted(texts)),
                "source": {"format": "pdf", "pages": page_count, "pages_without_text": empty_pages,
                           "ocr_pages": ocr_pages, "ocr_attempted_pages": attempted_pages,
                           "ocr_languages": ["spa", "eng"] if attempted_pages else []}, "warnings": warnings}
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError("No se ha podido leer el PDF. Puede estar dañado o usar un formato no compatible; prueba a exportarlo de nuevo.") from exc


def validate_upload(upload):
    if not isinstance(upload, dict):
        raise ValidationError("El archivo no tiene un formato válido.")
    name = upload.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 255:
        raise ValidationError("El nombre del archivo no es válido.")
    if "/" in name or "\\" in name or any(ord(c) < 32 for c in name):
        raise ValidationError("Usa un nombre de archivo sin rutas ni caracteres de control.")
    extension = PurePath(name).suffix.lower()
    if extension not in {".txt", ".md", ".pdf"}:
        raise ValidationError("Formato no admitido. Usa archivos .txt, .md o .pdf.")
    encoded = upload.get("content")
    if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_FILE_BYTES + 2) // 3):
        raise ValidationError("El archivo supera el límite de 1 MiB o no contiene texto válido.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValidationError("No se ha podido leer el archivo enviado.") from exc
    if len(raw) > MAX_FILE_BYTES:
        raise ValidationError("El archivo supera el límite de 1 MiB.")
    if extension == ".pdf":
        return {"name": name, "bytes": len(raw), **extract_pdf(raw)}
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("Guarda el archivo con codificación UTF-8 y vuelve a intentarlo.") from exc
    if not text.strip():
        raise ValidationError("El documento está vacío.")
    if any(unicodedata.category(c) == "Cc" and c not in "\n\r\t" for c in text):
        raise ValidationError("El documento contiene datos binarios o caracteres de control.")
    return {"name": name, "bytes": len(raw), "text": text}


def analyze_document(document):
    text = unicodedata.normalize("NFC", document["text"]).replace("\r\n", "\n").replace("\r", "\n")
    words = re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", text, flags=re.UNICODE)
    counts = Counter(word.casefold() for word in words if len(word) > 2 and word.casefold() not in STOP_WORDS)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    preview = re.sub(r"\s+", " ", paragraphs[0])
    return {
        "name": document["name"], "bytes": document["bytes"],
        "source": document.get("source", {"format": PurePath(document["name"]).suffix.lower().lstrip(".")}),
        "warnings": document.get("warnings", []),
        "statistics": {"words": len(words), "characters": len(text),
                       "lines": len(text.splitlines()), "paragraphs": len(paragraphs)},
        "keywords": [{"word": word, "count": count} for word, count in counts.most_common(8)],
        "preview": preview[:500] + ("…" if len(preview) > 500 else ""),
    }


def process_upload(upload, *, simulate_transient=False, worker=analyze_document):
    attempts = 0

    def execute(document):
        nonlocal attempts
        attempts += 1
        if simulate_transient and attempts == 1:
            raise TransientProcessingError("Fallo temporal simulado.")
        try:
            return worker(document)
        except OSError as exc:
            if exc.errno in {errno.EAGAIN, errno.EBUSY, errno.ETIMEDOUT, errno.EINTR}:
                raise TransientProcessingError("La operación está temporalmente ocupada.") from exc
            raise

    # La validación queda fuera del tramo con reintentos.
    pipeline = RunnableLambda(validate_upload) | RunnableLambda(execute).with_retry(
        retry_if_exception_type=(TransientProcessingError,),
        stop_after_attempt=MAX_ATTEMPTS,
        wait_exponential_jitter=True,
        exponential_jitter_params={"multiplier": 0.1, "max": 0.5, "jitter": 0.1},
    )
    name = upload.get("name", "Sin nombre") if isinstance(upload, dict) else "Sin nombre"
    try:
        result = pipeline.invoke(upload)
        return {**result, "status": "ok", "attempts": attempts, "demo": simulate_transient}
    except ValidationError as exc:
        message, kind = str(exc), "validation"
    except TransientProcessingError:
        message, kind = "El fallo temporal continúa después de 3 intentos. Puedes volver a procesar el archivo.", "transient"
    except Exception:
        message, kind = "No se pudo procesar el documento. Revisa el archivo y vuelve a intentarlo.", "processing"
    return {"name": name if isinstance(name, str) else "Sin nombre", "status": "error",
            "attempts": attempts, "error": message, "error_type": kind, "demo": simulate_transient}


def process_batch(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        raise ValidationError("Selecciona al menos un archivo.")
    files = payload["files"]
    if not 1 <= len(files) <= MAX_FILES:
        raise ValidationError("Puedes procesar entre 1 y 10 archivos por lote.")
    demo = payload.get("simulate_transient", False)
    if not isinstance(demo, bool):
        raise ValidationError("La opción de simulación no es válida.")
    results = [process_upload(item, simulate_transient=demo) for item in files]
    return {"version": 1, "mode": "local-deterministic", "results": results,
            "summary": {"total": len(results), "ok": sum(r["status"] == "ok" for r in results),
                        "errors": sum(r["status"] == "error" for r in results)}}
