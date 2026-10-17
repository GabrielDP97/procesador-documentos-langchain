# Procesador de documentos con LangChain Core

Proyecto para crear una aplicación local que procese documentos y reintente automáticamente operaciones que fallen de forma temporal.

## Estado

Repositorio inicial preparado. La aplicación todavía está pendiente de desarrollo.

## Objetivo del primer prototipo

- Seleccionar archivos de texto `.txt` y `.md`.
- Validar su formato y leer su contenido en el ordenador.
- Procesarlos mediante funciones locales y componentes `Runnable` de LangChain Core.
- Aplicar reintentos limitados a fallos temporales, sin repetir errores permanentes como formatos no admitidos.
- Mostrar el resultado de cada archivo y permitir exportarlo a JSON.
- Incorporar una interfaz en español una vez probado el procesamiento.

## Requisitos y coste

Python 3.10 o posterior. El primer prototipo funcionará con CPU, sin modelos de IA, claves de API, cuentas externas ni servicios de pago. No necesita LangSmith. El alojamiento externo y el uso de Codex se valorarían por separado.

LangChain Core utiliza licencia MIT. La licencia y los requisitos actuales se comprobarán antes de fijar la versión para el desarrollo.

## Preparar el entorno en Windows

Abre esta carpeta en Codex o en una terminal de PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Estos pasos preparan el entorno; no arrancan una aplicación todavía.

## Plan de desarrollo

1. Fijar la versión de LangChain Core y comprobar `RunnableLambda.with_retry`.
2. Implementar procesamiento y exportación de archivos con límites de tamaño.
3. Probar errores temporales, errores permanentes y el número máximo de intentos.
4. Crear una interfaz local para seleccionar archivos y revisar resultados.
5. Verificar el flujo completo con los documentos sintéticos de `ejemplos/`.

## Referencias

- [Instalación de LangChain](https://docs.langchain.com/oss/python/langchain/install).
- [Código y licencia de LangChain](https://github.com/langchain-ai/langchain).
- [Noticia de origen: langchain-core 1.6.9](https://github.com/langchain-ai/langchain/releases/tag/langchain-core%3D%3D1.6.9).

No subas documentos personales, resultados privados, credenciales ni el entorno `.venv` al repositorio.
