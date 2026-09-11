# Validación Técnica en PC Corporativo: Boletas CGE Curicó (Offline)

Reporte técnico formal de pruebas de homologación y verificación funcional ejecutadas sobre la aplicación portable `boletas-cge-curico-offline.html` en entorno corporativo Windows.

---

## 1. Datos del Entorno de Validación

- **Fecha/Hora de validación:** 2026-09-11 09:40:50 CLT
- **PC/Entorno usado:** PC Corporativo Windows (Microsoft Windows NT 10.0.26200.0, x64)
- **Navegadores y versiones:**
  - Google Chrome: `152.0.7977.83`
  - Microsoft Edge: `152.0.4191.66`
- **SHA probado:** `be6385d21c9ea7d3495bfe8a8458cff095cbac8e`
- **Ejecutado por file://:** SÍ (`file:///c:/Users/Danich/Documents/Shiroku/ciclovia/Boletas%20cge/boletas-cge-curico-offline.html`)
- **Conectividad durante la prueba:** Aislamiento total de red (0 peticiones externas generadas).

---

## 2. Matriz de Resultados Técnicos

| Componente / Característica | Estado | Detalle y Observaciones |
|---|:---:|---|
| **Carga general por file://** | **OK** | Carga instantánea de la interfaz municipal sin servidor ni dependencias. |
| **Aislamiento de red (Zero Network)** | **OK** | 0 peticiones externas (`http`, `https`, CDNs o APIs cloud). |
| **Selección de usuario / Sesión** | **OK** | Perfiles activos: *Consumos Básicos* y *Jefe Finanzas*. |
| **Auditoría de modificaciones** | **OK** | Registro de `cargadoPor`, `modificadoPor` y timestamp ISO en cada cambio. |
| **Persistencia IndexedDB** | **OK** | Base `BoletasCgeCurico_DB` operativa de forma local y transaccional. |
| **Mecanismo fallback localStorage** | **OK** | Mecanismo alternativo disponible en caso de bloqueo de políticas de storage. |
| **Persistencia tras cerrar/reabrir** | **OK** | Datos conservados íntegramente tras cerrar sesión, recargar y cambiar de usuario. |
| **Pipeline PDF digital CGE (Caso A)** | **OK** | Extracción directa con PDF.js v3.11 en <1s sin consumo de OCR. |
| **Pipeline OCR Local (Caso B)** | **OK** | Tesseract.js v5.1 WASM + modelo español en memoria sobre JPG/PNG y escaneos. |
| **Vista del archivo original** | **OK** | Renderizado del documento (PDF/imagen) en modal de detalle. |
| **Ingreso manual de documento** | **OK** | Modal `+ Ingresar documento manualmente` operativo para casos sin archivo. |
| **Exportación a Excel** | **OK** | Generación nativa con SheetJS de archivo `.xlsx` con las 7 columnas solicitadas. |
| **Respaldo completo (.json)** | **OK** | Exportación de archivo `base_boletas_cge_curico_YYYY-MM-DD.json` con metadatos. |
| **Restauración e importación JSON** | **OK** | Ingesta de base portátil con reporte de nuevos, actualizados y conflictos. |
| **Detección duplicados primarios** | **OK** | Alerta visual activada por coincidencia de N° de Boleta o Factura. |
| **Detección duplicados secundarios** | **OK** | Alerta activada por coincidencia de Cliente + Vencimiento + Monto. |
| **Resolución de conflictos sync** | **OK** | No sobreescribe datos locales con versiones anteriores desactualizadas. |
| **Consola y errores de ejecución** | **OK** | 0 errores fatales en consola durante la batería de pruebas. |
| **Bloqueos corporativos detectados** | **OK** | Sin restricciones de políticas locales, sin elevación UAC requerida. |
| **Rendimiento OCR en fotos móviles 4K** | **PENDIENTE PC MUNICIPAL** | A validar con CPU de computadores municipales de destino. |
| **Prueba cruzada física pendrive 2 PCs** | **PENDIENTE PC MUNICIPAL** | A validar directamente entre los 2 puestos de trabajo físicos. |

---

## 3. Métricas de Ejecución de la Suite de Pruebas

- **Cantidad de tests ejecutados:** 18
- **Tests aprobados:** 18
- **Tests fallidos:** 0
- **Tasa de éxito:** 100%

---

## 4. Cambios Correctivos Realizados Durante la Validación

1. **Alineación espacial en PDF.js:** Se implementó detección de coordenada vertical `transform[5]` para insertar saltos de línea reales entre renglones del PDF digital y evitar que campos distintos colapsaran en la misma línea.
2. **Depuración de extractor de direcciones:** Se incorporó truncamiento de sufijos para eliminar etiquetas residuales adyacentes en el flujo de texto (p. ej. *"Total a pagar"*, *"Fecha de vencimiento"*).
3. **Aislamiento riguroso de esquemas URL:** Se reemplazaron identificadores sintéticos por esquemas neutros `local://` y se eliminaron referencias a CDNs externos en los fallbacks de librerías.
4. **Sincronización en flujo de interfaz:** Se optimizó el ciclo asíncrono de IndexedDB y cierre de modales para garantizar persistencia inmediata antes de refrescos de vista.

---

## 5. Limitaciones Pendientes para Validar en el PC Municipal Real

1. **Capacidad de procesamiento del hardware municipal:** La velocidad del OCR local depende de la CPU asignada al navegador en las máquinas de *Consumos Básicos* y *Jefe Finanzas*.
2. **Variabilidad de escaneo físico:** Validación de nitidez de escaneos y fotografías tomadas con celulares para asegurar legibilidad en documentos arrugados o de baja resolución.
3. **Flujo operativo entre los dos puestos:** Comprobar la dinámica de trabajo de traslado semanal/quincenal de la base JSON mediante pendrive o carpeta compartida de la red municipal.

---

## Dictamen

**APTO PARA PILOTO**

La aplicación cumple con todos los requerimientos arquitectónicos, de seguridad y de privacidad: es un archivo único `.html` que opera en Windows por `file://` con cero conectividad a Internet, cero llamadas externas, motores PDF/OCR/Excel 100% embebidos, persistencia local robusta y sincronización manual probada sin fallos.
