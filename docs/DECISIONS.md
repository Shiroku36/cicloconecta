# Registro de Decisiones de Arquitectura (ADR) — CicloConecta

Este documento registra las decisiones arquitectónicas clave tomadas durante el desarrollo de CicloConecta, su contexto, motivación y consecuencias técnicas.

---

## D-001 — MapLibre GL JS como Renderer Cartográfico

- **Fecha:** 2026-09-08
- **Estado:** Aceptada
- **Contexto:**
  Se requería un motor de mapas interactivo, moderno y libre para renderizar calles, etiquetas y capas vectoriales/GeoJSON personalizadas de infraestructura ciclista en el navegador.
- **Decisión:**
  Adoptar **MapLibre GL JS** (fork abierto de Mapbox GL JS v1/v2 libre de telemetría y licencias privativas) en conjunto con teselas cartográficas base libres de Carto Positron / OpenStreetMap.
- **Consecuencias:**
  - Positivas: Renderizado WebGL de alto rendimiento (60fps en zoom y paneo), soporte nativo de estilos vectoriales/raster, sin necesidad de tokens o costos por vista de mapa, desacoplado de proveedores privativos como Google Maps o Mapbox API.
  - Negativas: Requiere gestión explícita de capas GeoJSON y ciclo de vida en React (`useEffect`, `on('load')`).

---

## D-002 — Desacoplamiento Estricto: Preprocesamiento Batch vs Visualizador Liviano

- **Fecha:** 2026-09-08
- **Estado:** Aceptada
- **Contexto:**
  El cálculo de grafos viales, análisis de conectividad y detección de cortes requiere procesamiento topológico pesado. Si se ejecuta en cada carga del frontend, los tiempos de respuesta y costos de cómputo serían inaceptables.
- **Decisión:**
  Separar tajantemente el procesamiento de la visualización:
  1. Un proceso offline/batch (`pipeline/`) analiza una ciudad, calcula métricas, normaliza atributos y genera archivos GeoJSON y metadatos de ciudad.
  2. El frontend solo consume y superpone estas capas GeoJSON livianas sobre el mapa base.
- **Consecuencias:**
  - Positivas: Carga casi instantánea para los usuarios en la web, posibilidad de alojar capas en CDN o almacenamiento estático, reutilización total de cálculos previos.
  - Negativas: Las modificaciones en la red vial requieren ejecutar el pipeline para actualizar las capas exportadas.

---

## D-003 — Estructura de Datos Jerárquica por Ciudad (`cities/{city_id}/`)

- **Fecha:** 2026-09-08
- **Estado:** Aceptada
- **Contexto:**
  El objetivo del proyecto es escalar progresivamente a lo largo de Chile (comenzando en Curicó, extendiéndose a Talca, Rancagua, Concepción, Santiago, etc.). No debe ser necesario reescribir componentes del frontend para soportar una nueva ciudad.
- **Decisión:**
  Organizar los datos en una estructura de carpetas estándar:
  ```text
  data/cities/{city_id}/
    ├── city.json
    ├── cycling-infrastructure.geojson
    ├── missing-connections.geojson
    └── suggested-routes.geojson
  ```
- **Consecuencias:**
  - Positivas: Agregar una ciudad se reduce a añadir una carpeta y ejecutar el pipeline; el frontend y la API detectan dinámicamente las ciudades y sus capas disponibles.
  - Negativas: Para ciudades metropolitanas masivas con miles de kilómetros (ej. Gran Santiago), las capas GeoJSON monolíticas podrían requerir en el futuro particionamiento en teselas vectoriales (PMTiles / MVT).

---

## D-004 — Extracción Directa desde OpenStreetMap (Overpass API) para Curicó

- **Fecha:** 2026-09-08
- **Estado:** Aceptada
- **Contexto:**
  La primera iteración requería representar ciclovías reales de Curicó sin recurrir a datos inventados ni scraping de imágenes.
- **Decisión:**
  Consultar la API de Overpass de OpenStreetMap con filtros geográficos sobre el bounding box urbano de Curicó (`way["highway"="cycleway"]`, `way["cycleway"]`, `way["bicycle"="designated"]`), transformando la topología de nodos y vías en un FeatureCollection GeoJSON con cálculo geodésico de distancias.
- **Consecuencias:**
  - Positivas: Datos 100% verificables, reales y colaborativos (más de 120 tramos reales detectados en Curicó, 43+ km).
  - Negativas: Depende de la exhaustividad del mapeo de la comunidad local en OSM; tramos no etiquetados deben ser mapeados en OSM para aparecer.

---

## D-005 — Stack Frontend: Vite + React + TypeScript

- **Fecha:** 2026-09-08
- **Estado:** Aceptada
- **Contexto:**
  Se buscaba rapidez en desarrollo, tipado estricto para modelos geoespaciales y empaquetado ultra liviano.
- **Decisión:**
  Utilizar Vite como bundler, React 18/19 como biblioteca de UI y TypeScript en modo estricto.
- **Consecuencias:**
  - Positivas: Tiempos de recarga casi instantáneos (HMR), verificación estricta de tipos GeoJSON y contratos de API, bundle final mínimo.

---

## D-006 — Stack Backend: Python + FastAPI

- **Fecha:** 2026-09-08
- **Estado:** Aceptada
- **Contexto:**
  El ecosistema de análisis geoespacial en Python (Shapely, NetworkX, GeoPandas, OSMnx) es el estándar de la industria. Para la capa de servicio HTTP se requiere un framework ágil, asíncrono y de tipado robusto.
- **Decisión:**
  Utilizar FastAPI con modelos Pydantic y Uvicorn.
- **Consecuencias:**
  - Positivas: Documentación OpenAPI `/docs` generada automáticamente, validación de esquemas en tiempo de ejecución, compatibilidad directa con el pipeline Python existente.
  - Negativas: Ninguna significativa para el alcance actual.

---

## D-007 — Capa CicloConecta Maestra e Independencia del Mapa Base

- **Fecha:** 2026-09-08
- **Estado:** Aceptada
- **Contexto:**
  El concepto nuclear de CicloConecta es no competir con Google Maps ni recrear mapas base, sino superponer una capa propia de análisis de movilidad ciclista sobre el mapa existente, permitiendo al usuario encenderla o apagarla por completo sin recargar ni recalcular las teselas urbanas base.
- **Decisión:**
  Implementar un control maestro de visibilidad de la *Capa CicloConecta* en el componente `LayerControl` y `MapView`:
  1. Cuando la capa maestra se desactiva, todas las subcapas ciclistas (existentes, faltantes y sugeridas) se ocultan inmediatamente en el pipeline de WebGL (`setLayoutProperty('none')`), dejando solo el mapa base libre.
  2. Cuando se activa, se respeta el estado individual de cada subcapa.
- **Consecuencias:**
  - Positivas: Cumple al 100% con la separación conceptual entre "mapa base (contexto)" y "capa CicloConecta (datos propios)", permitiendo comparaciones instantáneas sin costo de cómputo.
  - Negativas: Ninguna.

---

## D-008 — Fuente Única de Verdad (`data/cities/`) y Sincronización Automática

- **Fecha:** 2026-09-09
- **Estado:** Aceptada
- **Contexto:**
  Para permitir que el frontend funcione tanto acoplado a la API FastAPI como en despliegue 100% estático (GitHub Pages, Vercel, S3), los archivos GeoJSON y de metadatos se consumen opcionalmente desde `frontend/public/data/cities/`. Sin embargo, mantener dos copias independientes creaba el riesgo de divergencia si se editaban manualmente.
- **Decisión:**
  Definir `data/cities/` como la **única fuente de verdad** canónica. Todo script de generación (`pipeline/osm_extractor.py`) o comando npm (`npm run sync:data`) sincroniza automáticamente los archivos procesados hacia `frontend/public/data/cities/` en la misma ejecución. Nunca se editan manualmente los archivos en `frontend/public/`.
- **Consecuencias:**
  - Positivas: Se preserva la portabilidad para despliegues estáticos sin servidor mientras se elimina el riesgo de divergencia entre backend y frontend.
  - Negativas: Requiere que cualquier regeneración de datos ejecute la sincronización (ya automatizada en el script).


