# Bitácora de Progreso — CicloConecta

Este documento actúa como la **fuente de verdad del desarrollo** entre agentes y colaboradores, registrando de forma cronológica y estructurada los avances, validaciones, problemas resueltos y temas pendientes del proyecto.

---

## [2026-09-09] — Iteración 1.1: Endurecimiento, Corrección de Renderizado y CI Verde

### 1. ¿Qué se hizo?
- **Corrección de Condición de Carrera en MapView:**
  - Se eliminó el riesgo de que las fuentes de MapLibre se inicialicen vacías o no se actualicen si los datos GeoJSON se resuelven antes o después de `map.on('load')`.
  - Se implementó `layersDataRef` y `syncMapLayers`, garantizando que al dispararse `map.on('load')` se carguen inmediatamente los datos más recientes sin importar el orden asíncrono, y que actualizaciones posteriores ejecuten `source.setData()` de manera segura y sin timeouts.
- **Resolución de CI en GitHub Actions:**
  - Diagnóstico del error real en CI: `pytest backend/tests/` fallaba con `ModuleNotFoundError: No module named 'backend'` porque `pytest` no agregaba el directorio raíz a `sys.path` en el runner de Linux.
  - Se creó `pytest.ini` configurando `pythonpath = .` y `testpaths = backend/tests`.
  - Se configuró `PYTHONPATH: .` en `.github/workflows/ci.yml` y se actualizó Node.js a la versión 22 para evitar deprecaciones en GitHub Actions.
- **Corrección Semántica de Datos OpenStreetMap:**
  - Se eliminó la etiqueta errónea `"OSM Verificado"` en la UI (`CityHeader`) reemplazándola por `"Datos OpenStreetMap"`.
  - Se ajustó el extractor `pipeline/osm_extractor.py` para **no inventar datos inexistentes**: si falta `surface` o `segregated` se guarda `None` (`"Sin información"` en display), sin asumir `"asfalto / pavimento"` ni `"yes"`.
  - Se preservan los tags originales en `properties.raw_osm_tags`.
- **Clasificación Transparente de Vías Ciclistas:**
  - Se diseñó la función `classify_osm_cycling_way()` clasificando con honestidad las vías en:
    * `Vía ciclista dedicada (segregada / cycleway)`
    * `Infraestructura ciclista sobre calle (segregada / track)`
    * `Infraestructura ciclista sobre calle (ciclobanda / lane)`
    * `Vía designada / preferente para bicicleta`
    * `Infraestructura ciclista compatible`
- **Seguridad en Popups Cartográficos:**
  - Se reemplazó la interpolación de strings HTML por manipulación segura del DOM (`document.createElement` + `textContent`) vía `popup.setDOMContent()`, protegiendo la aplicación contra vectores XSS provenientes de etiquetas libres de OSM.
- **Fuente de Verdad Única y Sincronización Automática (ADR D-008):**
  - Se estableció `data/cities/` como la única fuente de verdad. `pipeline/osm_extractor.py` copia y sincroniza automáticamente los datasets a `frontend/public/data/cities/` en cada ejecución.
  - Se añadió el comando `npm run sync:data` en el frontend.
- **Nuevos Tests Automatizados:**
  - Se creó `backend/tests/test_osm_classification.py` con 5 tests específicos validando la clasificación transparente, la ausencia de atributos inventados y la validez estructural de los GeoJSON (13 tests en total en la suite).

### 2. ¿Qué se verificó?
- `pytest`: **13/13 tests aprobados** (endpoints API + clasificación OSM).
- `npm --prefix frontend run lint`: **0 errores, 0 advertencias** con Oxlint.
- `npm --prefix frontend run build`: **Compilación exitosa** sin advertencias críticas.
- Visual: Verificado que las líneas verdes (OSM), ámbar (gaps) y azules (rutas) se renderizan correctamente sin importar el orden de carga, los popups son seguros y reflejan los datos fidedignos sin suposiciones.

### 3. ¿Qué problemas aparecieron y cómo se resolvieron?
- *CI fallaba en runner Linux:* Solucionado con `pytest.ini` (`pythonpath = .`) y variable de entorno en workflow.
- *Datos de superficie asumidos:* Solucionado normalizando a `None` / `Sin información`.
- *Vulnerabilidad potencial en popup HTML:* Solucionado con `setDOMContent` y nodos DOM seguros.

### 4. ¿Qué quedó pendiente para Fase 2?
- Algoritmo de detección automática de gaps mediante grafos en NetworkX.
- Expansión a la ciudad de Talca.

---

## [2026-09-08] — Iteración 1: Fundación y Vertical Slice de Curicó

### 1. ¿Qué se hizo?
- **Configuración del Repositorio:**
  - Inicialización del repositorio Git con rama principal `main`, licencia libre `MIT` y `.gitignore` estricto (Node, Python, Vite, variables `.env`).
  - Creación y publicación del repositorio público en GitHub: [`shiroku36/cicloconecta`](https://github.com/shiroku36/cicloconecta).
  - Configuración de integración continua (CI) en `.github/workflows/ci.yml` ejecutando tests de Python y lint/build de Vite en cada push/PR.
- **Pipeline de Datos y Datos Reales de Curicó:**
  - Desarrollo de `pipeline/osm_extractor.py` para consultar la API de Overpass de OpenStreetMap en el bounding box urbano de Curicó (`-35.05, -71.30, -34.93, -71.18`).
  - Extracción y normalización de **121 vías ciclistas reales (43.2 km)** a formato GeoJSON estándar (`data/cities/curico/cycling-infrastructure.geojson`), con cálculo de longitud geodésica y clasificación de superficie/segregación.
  - Generación de `data/cities/curico/city.json` con metadatos espaciales, centroide (`[-71.2394, -34.9854]`), bounding box y estadísticas agregadas.
  - Creación de datasets conceptuales claramente etiquetados como `DEMO` para validar la experiencia de usuario:
    - `missing-connections.geojson`: 3 conexiones críticas (Rauquén - Estación, O'Higgins - Av. España, Merced - Río Guaiquillo).
    - `suggested-routes.geojson`: 2 rutas barriales de bajo estrés vehicular (Zapallar - Plaza de Armas, Campus UTAL - Centro).
- **Backend API (FastAPI):**
  - Implementación de API REST liviana en `backend/app/main.py` con schemas Pydantic y CORS habilitado.
  - Endpoints: `GET /api/health`, `GET /api/cities`, `GET /api/cities/{city_id}`, `GET /api/cities/{city_id}/layers/{layer_id}`.
  - Suite de pruebas unitarias automatizadas con `pytest` en `backend/tests/test_api.py`.
- **Frontend Interactivo (React + TypeScript + Vite + MapLibre GL JS):**
  - Configuración de mapa base libre acelerado por WebGL (Carto Voyager / OSM) sin dependencias ni costos de APIs privativas.
  - Jerarquía de capas:
    - **Capa Maestra CicloConecta:** Control principal que permite encender/apagar toda la información ciclista en un solo click, dejando visible únicamente el mapa base sin recargarlo.
    - **Subcapas Especializadas:** Toggles individuales para *Ciclovías existentes* (verde esmeralda sólido `#10b981`), *Conexiones faltantes* (ámbar discontinuo `#f59e0b`) y *Rutas sugeridas* (azul ciclista `#3b82f6`).
  - Panel flotante `LayerControl` tipo glassmorphism con badges visuales `REAL` y `DEMO`, conteo dinámico de tramos y botón de centrado rápido (`flyTo`).
  - Popups interactivos al hacer click sobre cualquier tramo ciclista, mostrando nombre de calle, tipo de vía, superficie, longitud en km/m y atribución de fuente.
  - Modal `InfoModal` para transparencia metodológica comunitaria.
  - Resiliencia de carga: fallback inteligente a archivos estáticos locales (`public/data/cities/curico/`) si la API no está en ejecución.
- **Documentación Técnica:**
  - `README.md`: Guía de inicio rápido, arquitectura y comandos de verificación.
  - `docs/ARCHITECTURE.md`: Principios arquitectónicos (preprocesamiento offline vs visualizador liviano).
  - `docs/DATA_PIPELINE.md`: Especificación matemática y algorítmica del pipeline determinista.
  - `docs/DECISIONS.md`: Registro de Decisiones de Arquitectura (ADRs D-001 a D-007).
  - `docs/ROADMAP.md`: Plan de evolución en 5 fases hacia escala nacional.

---

### 2. ¿Qué se verificó?
- **Pipeline de Datos:**
  - Ejecución exitosa de `python pipeline/osm_extractor.py`, generando 121 features reales de Curicó con coordenadas válidas.
- **Pruebas Automatizadas de Backend:**
  - `pytest backend/tests/`: **8/8 tests aprobados** (salud, listado de ciudades, detalle de Curicó, GeoJSON válidos de ciclovías y conexiones demo, respuestas 404 para recursos inexistentes).
- **Calidad de Código Frontend:**
  - `npm --prefix frontend run lint`: **0 errores, 0 advertencias** con Oxlint.
  - `npm --prefix frontend run build`: Compilación limpia de TypeScript (`tsc -b`) y empaquetado de producción Vite en ~400 ms.
- **Ejecución en Vivo (E2E Manual):**
  - Servidor FastAPI corriendo en `http://127.0.0.1:8000` con respuestas HTTP 200 OK.
  - Servidor Vite corriendo en `http://127.0.0.1:5173` con proxy hacia backend funcionando.
  - Mapa WebGL renderizando correctamente las calles de Curicó.
  - Interruptor maestro de la *Capa CicloConecta* ocultando y mostrando todas las geometrías de forma instantánea sin parpadeos ni recálculos del mapa base.
  - Selección individual de subcapas operando fluidamente.
  - Popups respondiendo al click sobre vías con información detallada.
- **Control de Versiones:**
  - Historial de commits ordenado, descriptivo y sin secretos en el árbol de trabajo.
  - Sincronización exitosa con la rama `main` en GitHub.

---

### 3. ¿Qué problemas aparecieron y cómo se resolvieron?
1. **Cuenta activa de GitHub CLI:**
   - *Problema:* `gh` estaba configurado por defecto con la cuenta `Shiroku-D`, mientras que el proyecto debía pertenecer a `shiroku36`.
   - *Solución:* Se ejecutó `gh auth switch --user Shiroku36`, activando la cuenta correcta y permitiendo crear el repositorio público `shiroku36/cicloconecta` y vincular el remoto.
2. **Tipos e importaciones de MapLibre GL JS en TypeScript:**
   - *Problema:* En la versión 6.x de `maplibre-gl`, no existe exportación por defecto (`TS1192`), y los eventos de mouse en capas requerían tipado explícito (`MapLayerMouseEvent`).
   - *Solución:* Se ajustaron las importaciones a named imports (`{ Map as MapLibreMap, NavigationControl, Popup, ... }`) y se tiparon estrictamente los manejadores de eventos.
3. **Advertencia de hooks en React (`exhaustive-deps`):**
   - *Problema:* El hook de inicialización del mapa WebGL no debía re-ejecutarse al cambiar los estados de visibilidad de las capas, pues eso destruiría el canvas del mapa innecesariamente.
   - *Solución:* Se desacopló la inicialización del mapa en un efecto dedicado, mientras que la actualización de datos GeoJSON y la visibilidad de capas se gestionan en efectos reactivos independientes que operan sobre las propiedades del mapa ya instanciado (`setLayoutProperty` y `setData`).
4. **Distinción visual estricta entre datos reales y de prueba:**
   - *Problema:* Riesgo de que usuarios o evaluadores confundan las conexiones faltantes estimadas con ciclovías reales.
   - *Solución:* Se incorporaron badges visuales de alto contraste (`REAL` verde vs `DEMO` amarillo) tanto en el panel de capas como en los popups de cada tramo, además de documentar la procedencia en `metadata.source`.

---

### 4. ¿Qué quedó pendiente para siguientes iteraciones?
1. **Detector Algorítmico de Gaps (`pipeline/gap_detector.py`):**
   - Implementar el cálculo determinista con NetworkX/Shapely para sustituir las capas DEMO de Curicó por discontinuidades calculadas a partir del grafo vial completo.
2. **Selector Visual de Ciudades:**
   - Añadir un dropdown en la barra superior del frontend para cambiar de ciudad dinámicamente cuando se añada la segunda comuna.
3. **Expansión a la Segunda Ciudad (Talca):**
   - Correr el extractor para Talca y verificar la extensibilidad de la arquitectura `data/cities/talca/`.
4. **Filtros por Atributo en el Visor:**
   - Permitir filtrar por tipo de superficie (asfalto vs maicillo) o segregación física.
