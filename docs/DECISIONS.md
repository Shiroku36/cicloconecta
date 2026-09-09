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

---

## D-009 — Registro Explícito de MapLibre Web Worker y Mapa Base OpenStreetMap Sin API Key

- **Fecha:** 2026-09-09
- **Estado:** Aceptada
- **Contexto:**
  1. MapLibre GL JS v6 en entornos Vite intenta resolver por defecto su script de Web Worker (`maplibre-gl-worker.mjs`) relativo a `import.meta.url`, resolviendo a `.vite/deps/maplibre-gl-worker.mjs` que devuelve HTTP 404. Sin el Web Worker activo, el parsing y teselado de las capas GeoJSON quedaba bloqueado en `_isUpdatingWorker: true`, impidiendo el renderizado visual de las líneas sobre el lienzo WebGL.
  2. Las teselas raster de CARTO Voyager (`basemaps.cartocdn.com`) comenzaron a exigir autenticación obligatoria para acceso no registrado, estampando una marca de agua visual invasiva con el texto "API KEY REQUIRED carto.com/basemapsapikey" en cada tesela del mapa.
- **Decisión:**
  1. Registrar explícitamente el worker de MapLibre mediante `setWorkerUrl(maplibreWorkerUrl)` importando `maplibre-gl/dist/maplibre-gl-worker.mjs?url`. Esto instruye a Vite a servir el worker como recurso estático con código HTTP 200 en desarrollo y a empaquetarlo en `dist/assets/` en producción.
  2. Migrar el mapa base a las teselas estándar de **OpenStreetMap** (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`), las cuales son 100% abiertas, comunitarias, gratuitas, sin marcas de agua y sin requerir claves de API ni tokens de ningún proveedor privativo.
  3. Eliminar la verificación bloqueante `map.isStyleLoaded()` en la sincronización de capas GeoJSON de `MapView.tsx`, reemplazándola por una verificación de inicialización de capas (`isLayersInitializedRef`), permitiendo que `source.setData()` actualice la GPU independientemente del estado de carga de las teselas raster de fondo.
- **Consecuencias:**
  - Positivas: Renderizado inmediato y fluido de los 121 tramos de ciclovías reales (verde esmeralda), tramos DEMO (ámbar discontinuo) y rutas sugeridas (azul); eliminación total del aviso/marca de agua "API KEY REQUIRED"; independencia de terceros comerciales.
  - Negativas: Ninguna.

---

## D-010 — Motor de Routing Ciclista Determinista en Python con NetworkX y Heurística Admisible A*

- **Fecha:** 2026-09-09
- **Estado:** Aceptada
- **Contexto:**
  Para la Fase 2, se requería construir un motor de routing ciclista real para Curicó que priorice infraestructura ciclista y vías calmadas sobre la ruta más corta física, reemplazando las geometrías conceptuales DEMO por rutas algorítmicas que sigan fielmente la red vial real de OpenStreetMap.
  Existía la alternativa de emplear librerías pesadas como `osmnx`, la cual arrastra dependencias binarias nativas en C/C++ (`gdal`, `geopandas`, `fiona`, `pyproj`, `rtree`) que generan fricciones severas en entornos Windows y pipelines CI de GitHub Actions, además de ralentizar los tiempos de arranque.
- **Decisión:**
  1. Construir un motor propio y desacoplado utilizando **Python estándar + NetworkX (`nx.DiGraph`)**, sin dependencias nativas de GDAL.
  2. Implementar una función de costo determinista $\text{costo} = \text{distancia\_m} \times \text{penalización}$, con factores calibrados entre 0.70 (ciclovías segregadas) y 2.60 (arterias rápidas sin infraestructura), bloqueando autopistas y vías no transitables para bicicletas.
  3. Emplear el algoritmo **A*** con heurística geodésica $h(u, v) = \text{haversine}(u, v) \times 0.70$. Dado que $0.70$ es el factor de costo mínimo posible, la heurística es estrictamente admisible y monotónica, encontrando el camino óptimo en $< 15\text{ ms}$.
  4. Precomputar y serializar `nav_graph.json` para carga inmediata en memoria en FastAPI, permitiendo tiempos de respuesta de consulta interactiva $< 10\text{ ms}$.
  5. Dotar al backend de una caché de rutas bidireccional en memoria y disco (`routes_cache.json`) indexada por coordenadas geográficas redondeadas a 5 decimales.
- **Consecuencias:**
  - Positivas: Zero dependencias C++ complejas; portabilidad universal (Linux, Windows, macOS, Docker); cálculo instantáneo; validación y comparación automática con la ruta más corta física (+% ciclovía vs +% desvío).
  - Negativas: Requiere un paso previo de extracción y construcción del grafo al incorporar nuevas ciudades (automatizado en el pipeline).

---

## D-011 — Detector Algorítmico de Brechas de Red Ciclista y Puntuación Multicriterio

- **Fecha:** 2026-09-09
- **Estado:** Aceptada
- **Contexto:**
  La capa `missing-connections.geojson` se encontraba catalogada como DEMO con 3 líneas conceptuales dibujadas manualmente. Se requería reemplazarla íntegramente por un detector algorítmico determinista que descubra oportunidades reales donde una conexión corta mejore significativamente la conectividad de la red ciclista existente en Curicó.
- **Decisión:**
  1. Extraer el subgrafo de ciclovías dedicadas $G_{\text{cycling}}$ a partir del grafo navegable $G_{\text{nav}}$ y descomponerlo en componentes conexas independientes (31 en Curicó, componente principal de 19,12 km y secundaria de 4,38 km).
  2. Detectar extremos abruptos (nodos de grado 1 en ciclovías $\ge 200\text{ m}$) y buscar caminos conectores sobre la red vial real ($G_{\text{nav}}$), respetando sentidos de circulación y topología real (puentes, cruces peatonales y sin atravesar obstáculos sin vía).
  3. Formular un índice de prioridad multicriterio transparente y acotado (0 a 100 pts) compuesto por:
     - Impacto territorial de red (0–50 pts): proporcional a la raíz cuadrada de la componente menor y al logaritmo de la red unificada.
     - Eficiencia y compacidad de la brecha (0–35 pts): penalización lineal decreciente por longitud de brecha hasta 1.200 m.
     - Confort y seguridad vial (0–15 pts): preferencia por vías locales/residenciales de bajo estrés vehicular.
  4. Deduplicar propuestas por par de componentes y filtrar solapamiento espacial (> 60%) para entregar un ranking claro de las mejores 10 oportunidades.
  5. Incorporar el panel `OpportunitiesList` en el frontend, permitiendo enfocar interactivamente cada oportunidad con resaltado y métricas transparentes.
  6. Utilizar terminología comunitaria prudente ("Conexión potencial", "Oportunidad detectada", "Candidato analítico") con aclaraciones explícitas de que no constituyen proyectos de ingeniería vial aprobados.
- **Consecuencias:**
  - Positivas: Eliminación definitiva de datos sintéticos DEMO; identificación de oportunidades reales de alto impacto (ej. brecha de 75 m en Manuel Antonio Caro que une 19,62 km, y brecha de 834 m en Enrique Lafourcade que unifica 24,33 km continuos); experiencia interactiva y visual atractiva.
  - Negativas: Requiere calibrar umbrales de búsqueda de distancia máxima (establecido en 1.200 m) para ciudades con morfología muy dispersa.




