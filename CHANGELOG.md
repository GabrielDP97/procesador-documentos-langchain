# Historial de versiones

## Documentación · 2026-10-18

- Instalación desde la clonación en Windows y Ubuntu/Debian.
- Explicación del papel de LangChain, diagrama del flujo, tabla de límites y solución de problemas.
- Guía de contribución y captura actualizada con documentos sintéticos.

## 1.1.1 · 2026-10-18

- Ampliado a 60 segundos el OCR por página para libros con páginas densas.

## 1.1.0 · 2026-10-18

- PDF de hasta 150 MiB y 1000 páginas; TXT/Markdown conservan el máximo de 1 MiB.
- Subida binaria sin base64, cola local acotada, progreso por páginas y cancelación.
- OCR alemán/inglés, español/inglés o inglés; hasta 1000 páginas y 2 horas de OCR por PDF.
- Copias temporales locales eliminadas al terminar, fallar o cancelar. Sin envío de documentos a servicios externos.

## 1.0.0 · 18 de octubre de 2026

Primera versión local funcional.

- Interfaz en español con selección de archivos y un ejemplo incorporado.
- TXT, Markdown y PDF; detección de archivos vacíos, corruptos y protegidos.
- OCR automático local en español e inglés para páginas sin texto, conservando el orden de los PDF mixtos.
- Estadísticas, palabras frecuentes, extracto inicial y exportación JSON por lote.
- Procesamiento con LangChain Core y reintentos acotados a errores temporales.
- Límites de tamaño, páginas, recursos de renderizado y tiempos de OCR.
- Documentos en memoria y servidor restringido a la dirección local.
- 27 pruebas, incluida una integración real de OCR, y comprobaciones automáticas en GitHub.

El análisis es determinista: no genera resúmenes ni interpreta documentos con un modelo de lenguaje. La aplicación está preparada para uso local; no es un servidor público multiusuario.
