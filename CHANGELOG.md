# Historial de versiones

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
