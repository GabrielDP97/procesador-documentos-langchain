# Colaborar en Documento

La aplicación procesa documentos en local. Los cambios deben mantener el funcionamiento sin servicios externos ni claves de API.

## Preparar el entorno

Sigue la instalación del [README](README.md). Usa Python 3.10 o posterior y las versiones de `requirements-lock.txt`. Instala Tesseract con `spa`, `eng` y `deu` para verificar el OCR.

## Comprobar un cambio

Desde la raíz del repositorio:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m pip check
node --check web/app.js
```

En Linux sustituye `.venv\Scripts\python.exe` por `.venv/bin/python`. La integración continua instala los idiomas de Tesseract y comprueba el OCR real.

Para cambios en la interfaz, arranca `app.py`, carga el ejemplo y comprueba el resultado y la exportación JSON. Si cambias la subida o la cola, revisa también progreso, cancelación y recuperación tras recargar. Usa los PDF sintéticos de `tests/pdf_fixtures.py` para las pruebas automatizadas.

## Preparar una contribución

- Explica el problema y el comportamiento resultante en la pull request.
- Incluye pruebas cuando cambie la lógica de extracción, validación, reintentos o trabajos en segundo plano.
- Actualiza el README y el historial si cambian límites o instrucciones.
- Mantén las capturas y ejemplos libres de documentos personales, credenciales y contenido de terceros.

`.private/`, `.venv/`, `entrada/`, `salida/`, resultados de prueba y archivos de entorno quedan fuera del repositorio. No añadas documentos reales para reproducir un error; prepara un caso sintético equivalente.
