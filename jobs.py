"""Trabajos locales acotados y copias temporales eliminadas al terminar."""
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import unquote
from processor import MAX_FILE_BYTES, MAX_PDF_FILE_BYTES, process_file, ValidationError


class Jobs:
    def __init__(self):
        self.lock = threading.RLock()
        self.slots = threading.BoundedSemaphore(2)
        self.worker = threading.Lock()
        self.items = {}
        self.threads = set()

    def reserve(self, encoded_name, languages, size, demo=False):
        name = unquote(encoded_name)
        if not name.strip() or len(name) > 255 or re.search(r"[/\\\x00-\x1f]", name):
            raise ValidationError("Nombre de archivo no válido.")
        suffix = Path(name).suffix.lower()
        if suffix not in {".pdf", ".txt", ".md"}:
            raise ValidationError("Usa TXT, Markdown o PDF.")
        limit = MAX_PDF_FILE_BYTES if suffix == ".pdf" else MAX_FILE_BYTES
        if not 0 < size <= limit:
            raise ValidationError("PDF: máximo 150 MiB. TXT/MD: máximo 1 MiB. El archivo no puede estar vacío.")
        if languages not in {"spa+eng", "deu+eng", "eng"}:
            raise ValidationError("Idioma de OCR no válido.")
        if not self.slots.acquire(blocking=False):
            return None
        try:
            handle = tempfile.NamedTemporaryFile(prefix="documento-", suffix=suffix, delete=False)
            token = uuid.uuid4().hex
            job = {"id": token, "status": "uploading", "name": name,
                   "progress": {"stage": "Subida", "done": 0, "total": size},
                   "cancel": threading.Event(), "path": Path(handle.name), "handle": handle,
                   "languages": languages, "demo": demo, "updated": time.monotonic()}
            with self.lock:
                for key, old in list(self.items.items()):
                    if old["status"] in {"done", "cancelled"} and time.monotonic() - old["updated"] > 3600:
                        del self.items[key]
                finished = [key for key, old in self.items.items() if old["status"] in {"done", "cancelled"}]
                for key in finished[:-100]:
                    del self.items[key]
                self.items[token] = job
            return job
        except Exception:
            self.slots.release()
            raise

    def snapshot(self, token):
        with self.lock:
            job = self.items.get(token)
            if not job:
                return None
            if job["status"] in {"done", "cancelled"} and time.monotonic() - job["updated"] > 3600:
                del self.items[token]
                return None
            return {key: job[key] for key in ("id", "status", "name", "languages", "progress", "result") if key in job}

    def cleanup(self, job):
        job["handle"].close()
        job["path"].unlink(missing_ok=True)
        self.slots.release()

    def abandon(self, job):
        self.cleanup(job)
        with self.lock:
            self.items.pop(job["id"], None)

    def start(self, job):
        job["handle"].close()
        job["status"] = "queued"
        thread = threading.Thread(target=self.run, args=(job,), daemon=True)
        with self.lock:
            self.threads.add(thread)
        thread.start()

    def run(self, job):
        def progress(stage, done, total):
            with self.lock:
                job["progress"] = {"stage": stage, "done": done, "total": total}
        try:
            while not self.worker.acquire(timeout=0.2):
                if job["cancel"].is_set():
                    break
            else:
                job["owns_worker"] = True
            try:
                job["status"] = "processing"
                result = process_file(job["path"], job["name"], languages=job["languages"],
                                      progress=progress, cancel=job["cancel"], simulate_transient=job["demo"])
            finally:
                if job.pop("owns_worker", False):
                    self.worker.release()
            with self.lock:
                job["result"] = result
        except Exception:
            with self.lock:
                job["result"] = {"name": job["name"], "status": "error", "attempts": 0,
                                 "error": "No se pudo procesar el documento.", "error_type": "processing"}
        finally:
            self.cleanup(job)
            job["updated"] = time.monotonic()
            with self.lock:
                job["status"] = "cancelled" if job["cancel"].is_set() else "done"
                self.threads.discard(threading.current_thread())

    def cancel(self, token):
        with self.lock:
            job = self.items.get(token)
            if not job:
                return False
            job["cancel"].set()
            return True

    def close(self):
        with self.lock:
            for job in self.items.values():
                job["cancel"].set()
            threads = list(self.threads)
        for thread in threads:
            thread.join(timeout=25)
