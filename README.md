# Documento · Procesador local con LangChain Core

Aplicación en español para procesar archivos `.txt` y `.md` en tu ordenador. Funciona con Python y CPU, sin claves de API, modelos, cuentas externas ni servicios de pago.

## Empezar en Windows

Requiere Python 3.10 o posterior. Desde esta carpeta en PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe app.py
```

Abre **http://127.0.0.1:8765**. Con el entorno instalado, también puedes hacer doble clic en `iniciar.cmd`. Mantén la terminal abierta mientras usas la aplicación; Ctrl+C detiene el servidor. Si el puerto está ocupado, usa `app.py --port 8766`.

## Qué puedes hacer

- Arrastrar o seleccionar hasta 10 archivos TXT o Markdown, UTF-8, de hasta 1 MiB por archivo.
- Cargar un ejemplo incorporado o los documentos sintéticos de `ejemplos/`.
- Ver palabras, caracteres, líneas, párrafos y ocho palabras frecuentes, filtrando palabras comunes españolas e inglesas.
- Leer una vista previa del primer párrafo, de hasta 500 caracteres. **Es un extracto, no un resumen ni una interpretación con IA.** Markdown se trata como texto; no se ejecuta ni renderiza HTML.
- Revisar errores por archivo sin perder los resultados de los otros documentos.
- Descargar el lote completo a JSON, incluidos los errores y el número de intentos.
- Activar «Probar la recuperación ante fallos»: simula un fallo temporal en el primer intento de cada archivo válido. El resultado debe mostrar 2 intentos. Está desactivada inicialmente.

Esta versión admite texto; no incluye PDF, Word, OCR, traducción ni conexión con el recopilador de noticias.

## Cómo funciona

`processor.py` utiliza una cadena de `RunnableLambda` de LangChain Core: validación → análisis. Solo el análisis lleva `with_retry`; los formatos inválidos, archivos vacíos, binarios, errores de UTF-8 y tamaños excesivos se rechazan antes de ejecutarlo.

Los errores temporales (`TransientProcessingError` y errores de sistema EAGAIN, EBUSY, ETIMEDOUT y EINTR) tienen un máximo de **3 intentos en total**, con esperas cortas. Los errores permanentes no se reintentan. Cada archivo usa una cadena independiente para conservar correctamente los resultados de los lotes mixtos.

El análisis es determinista. LangChain Core aporta la composición y los reintentos. Versión probada: **1.6.9**, licencia MIT. `requirements-lock.txt` fija las dependencias del entorno validado en Windows/Python 3.10; `requirements.txt` declara la dependencia principal.

## Privacidad y funcionamiento local

El servidor escucha únicamente en `127.0.0.1`, exige origen local para procesar y solo sirve los tres recursos públicos de `web/`. Documentos y resultados se mantienen en memoria, sin escribirlos al disco ni registrar su contenido. El navegador conserva los últimos resultados mientras la página siga abierta; solo la exportación crea un archivo descargado.

No se hacen peticiones externas al procesar. LangSmith viene como dependencia de LangChain Core, pero el proyecto desactiva su trazado. La instalación inicial sí requiere internet para descargar paquetes. Este servidor está diseñado para uso local.

## Comprobar la aplicación

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas cubren texto en español, métricas, UTF-8/BOM, límites, recuperación y agotamiento de reintentos, errores permanentes, lotes mixtos y servidor HTTP local.

Comprobación manual: carga el ejemplo, procésalo, activa la simulación, vuelve a procesarlo y exporta JSON. Prueba también un TXT vacío para ver su error junto a los demás resultados.

## Referencias

- [LangChain Core](https://github.com/langchain-ai/langchain/tree/master/libs/core).
- [Runnable.with_retry](https://reference.langchain.com/python/langchain-core/runnables/base/Runnable/with_retry).
- [Noticia de origen: langchain-core 1.6.9](https://github.com/langchain-ai/langchain/releases/tag/langchain-core%3D%3D1.6.9).

No subas documentos personales, resultados privados, credenciales ni `.venv` al repositorio.
