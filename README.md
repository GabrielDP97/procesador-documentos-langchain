# Documento · Procesador local con LangChain Core

Aplicación en español para procesar archivos `.txt`, `.md` y PDF, incluidos escaneados, en tu ordenador. Funciona con Python y CPU, sin claves de API, cuentas externas ni servicios de pago.

## Empezar en Windows

Requiere Python 3.10 o posterior. Desde esta carpeta en PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe app.py
```

Abre **http://127.0.0.1:8765**. Con el entorno instalado, también puedes hacer doble clic en `iniciar.cmd`. Mantén la terminal abierta mientras usas la aplicación; Ctrl+C detiene el servidor. Si el puerto está ocupado, usa `app.py --port 8766`.

## Qué puedes hacer

- Arrastrar o seleccionar hasta 10 archivos TXT, Markdown o PDF, de hasta 1 MiB por archivo. TXT/Markdown deben estar en UTF-8.
- Extraer el texto de todas las páginas de un PDF (hasta 100 páginas), con `pypdf`, en memoria y sin conexiones externas. En páginas sin texto, aplicar OCR local automáticamente con PDFium y Tesseract en español e inglés. Se indica qué páginas se han reconocido y cuáles siguen sin texto.
- Cargar un ejemplo incorporado o los documentos sintéticos de `ejemplos/`.
- Ver palabras, caracteres, líneas, párrafos y ocho palabras frecuentes, filtrando palabras comunes españolas e inglesas.
- Leer una vista previa del primer párrafo, de hasta 500 caracteres. **Es un extracto, no un resumen ni una interpretación con IA.** Markdown se trata como texto; no se ejecuta ni renderiza HTML.
- Revisar errores por archivo sin perder los resultados de los otros documentos.
- Descargar el lote completo a JSON, incluidos los errores y el número de intentos.
- Activar «Probar la recuperación ante fallos»: simula un fallo temporal en el primer intento de cada archivo válido. El resultado debe mostrar 2 intentos. Está desactivada inicialmente.

Los PDF escaneados sin capa de texto pasan por OCR automáticamente. Los PDF mixtos conservan el texto digital y aplican OCR solo a las páginas sin texto, respetando su orden. El reconocimiento puede cometer errores: revisa nombres, cifras y texto poco legible. No se vuelve a reconocer una página que ya tenga texto extraíble. Los PDF cifrados se rechazan con una indicación para guardar una copia sin contraseña. También se detectan PDF dañados o archivos cuya extensión se cambió sin convertirlos.

El orden de lectura y la separación de párrafos dependen del texto extraído del PDF: tablas y columnas pueden perder su disposición visual. Las estadísticas se calculan sobre ese texto y el reconocido con OCR. El límite adicional es 1 millón de caracteres y 5 MiB de contenido de página descomprimido por PDF; si se supera, se pide dividir el documento. No incluye Word, traducción ni conexión con el recopilador de noticias.

## OCR local

Además de instalar `requirements-lock.txt`, necesitas **Tesseract** con los idiomas `spa` y `eng`. En el ordenador de desarrollo ya está instalado y comprobado. Para otro equipo, consulta la [instalación de Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html) e incluye español e inglés. Comprueba la instalación con:

```powershell
tesseract --list-langs
```

La aplicación busca `tesseract` en PATH y en `C:/Program Files/Tesseract-OCR/`. Para una ubicación distinta puedes definir `TESSERACT_CMD` antes de arrancarla. Si faltan el programa o los idiomas, verás instrucciones en el resultado; los PDF con texto digital siguen funcionando.

El OCR admite hasta **20 páginas sin texto por PDF**, 20 segundos por página y un presupuesto de 120 segundos por documento (además del tiempo de renderizado). Renderiza a unos 200 ppp, reduciendo la resolución si hace falta para limitar la imagen a 8 millones de píxeles. PDFium se usa bajo un bloqueo porque no admite llamadas concurrentes. Tesseract recibe las imágenes por la entrada estándar y devuelve texto por la salida estándar: no se escriben imágenes temporales ni se envía contenido a internet. No se genera un PDF nuevo con capa de texto; el resultado se muestra en la aplicación y se exporta a JSON.

## Cómo funciona

`processor.py` utiliza una cadena de `RunnableLambda` de LangChain Core: validación y lectura/extracción → análisis. Solo el análisis lleva `with_retry`; los formatos inválidos, archivos vacíos, binarios, errores de UTF-8, PDF no compatibles y tamaños excesivos se rechazan antes de ejecutarlo.

Los errores temporales (`TransientProcessingError` y errores de sistema EAGAIN, EBUSY, ETIMEDOUT y EINTR) tienen un máximo de **3 intentos en total**, con esperas cortas. Los errores permanentes no se reintentan. Cada archivo usa una cadena independiente para conservar correctamente los resultados de los lotes mixtos.

El análisis es determinista. LangChain Core aporta la composición y los reintentos. Versión probada: **1.6.9**, licencia MIT. `requirements-lock.txt` fija las dependencias del entorno validado en Windows/Python 3.10; `requirements.txt` declara la dependencia principal.

## Privacidad y funcionamiento local

El servidor escucha únicamente en `127.0.0.1`, exige origen local para procesar y solo sirve los tres recursos públicos de `web/`. Documentos y resultados se mantienen en memoria, sin escribirlos al disco ni registrar su contenido. El navegador conserva los últimos resultados mientras la página siga abierta; solo la exportación crea un archivo descargado.

No se hacen peticiones externas al procesar. LangSmith viene como dependencia de LangChain Core, pero el proyecto desactiva su trazado. La instalación inicial sí requiere internet para descargar paquetes. Este servidor está diseñado para uso local.

## Comprobar la aplicación

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas cubren texto en español, métricas, UTF-8/BOM, límites, recuperación y agotamiento de reintentos, errores permanentes, PDF de varias páginas, escaneados, cifrados y dañados, OCR de páginas mixtas en orden, OCR ausente y tiempos límite, avisos de extracción parcial, lotes mixtos, exportación y servidor HTTP local. Los PDF de prueba se generan en memoria, sin documentos personales. La prueba real de OCR se omite si no está instalado Tesseract con español e inglés.

Comprobación manual: carga el ejemplo, procésalo, activa la simulación, vuelve a procesarlo y exporta JSON. Prueba también un TXT vacío para ver su error junto a los demás resultados.

## Referencias

- [LangChain Core](https://github.com/langchain-ai/langchain/tree/master/libs/core).
- [Runnable.with_retry](https://reference.langchain.com/python/langchain-core/runnables/base/Runnable/with_retry).
- [Extracción de texto con pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).
- [Tesseract OCR](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html).
- [Noticia de origen: langchain-core 1.6.9](https://github.com/langchain-ai/langchain/releases/tag/langchain-core%3D%3D1.6.9).

No subas documentos personales, resultados privados, credenciales ni `.venv` al repositorio.
