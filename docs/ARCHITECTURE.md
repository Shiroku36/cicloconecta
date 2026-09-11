# Arquitectura de CicloConecta

CicloConecta es una plataforma comunitaria diseñada para visualizar, diagnosticar y proyectar la movilidad ciclista en ciudades chilenas. Su diseño técnico prioriza la accesibilidad, velocidad de respuesta y modularidad para incorporar nuevas comunas sin rediseñar la aplicación.

---

## 1. Visión General del Sistema

El principio fundamental del sistema es la **separación estricta entre cómputo geoespacial (offline/batch) y consumo visual (cliente ligero)**.

```
┌────────────────────────────────────────────────────────┐
│                   PIPELINE GEOESPACIAL                 │
│              (Determinista, Python, Offline)           │
│                                                        │
│  OpenStreetMap (Overpass) / Fuentes Municipales        │
│                         │                              │
│                         ▼                              │
│             Extracción y Normalización                 │
│                         │                              │
│                         ▼                              │
│               Construcción de Grafo                    │
│        (Topología vial, sentidos, segregación)         │
│                         │                              │
│                         ▼                              │
│          Análisis de Gaps y Conectividad               │
│                         │                              │
│                         ▼                              │
│              Generación de GeoJSON / Metadatos         │
└─────────────────────────┬──────────────────────────────┘
                          │
                          ▼
            data/cities/{city_id}/*.geojson
                          │
         ┌────────────────┴────────────────┐
         ▼                                 ▼
┌──────────────────┐             ┌─────────────────────┐
│  FASTAPI BACKEND │             │  ESTÁTICO / CDN     │
│  /api/cities     │             │  (Hosting alterno)  │
│  /api/layers     │             │                     │
└────────┬─────────┘             └──────────┬──────────┘
         │                                  │
         └────────────────┬─────────────────┘
                          │ HTTP / JSON
                          ▼
┌────────────────────────────────────────────────────────┐
│                    FRONTEND CLIENTE                    │
│          (Vite + React + TypeScript + MapLibre)        │
│                                                        │
│  - Mapa Base: Teselas cartográficas Carto/OSM         │
│  - Capas Vectoriales CicloConecta:                     │
│      * Verde: Ciclovías existentes (reales)            │
│      * Ámbar: Conexiones faltantes (gaps prioritarios) │
│      * Azul: Rutas sugeridas / de bajo estrés          │
│  - Panel flotante de capas (toggle reactivo)           │
│  - Ficha informativa de segmentos al hacer click       │
│  - Selector de ciudades extensible                     │
└────────────────────────────────────────────────────────┘
```

---

## 2. Componentes

### 2.1. Pipeline Geoespacial (`pipeline/`)
- **Propósito:** Extraer datos viales crudos, filtrar elementos ciclistas, normalizar nombres y atributos, y estructurar geometrías GeoJSON estándar.
- **Filosofía Algorítmica:** Algoritmos matemáticos y de teoría de grafos deterministas para calcular distancias, conectividad de componentes, rutas más cortas y detección de brechas (gaps) estructurales. No se utilizan modelos de lenguaje para cálculos espaciales ni topológicos.
- **Módulos Principales:**
  - `osm_extractor.py`: Extracción y normalización de infraestructura ciclista existente desde OSM.
  - `network_extractor.py` & `graph_builder.py`: Descarga y construcción del grafo navegable multimodal ($G_{\text{nav}}$).
  - `router.py`: Motor de búsqueda de rutas ciclistas óptimas con A* heurístico.
  - `gap_detector.py`: Extracción del subgrafo ciclista segregado ($G_{\text{cycling}}$), identificación de componentes conexas, búsqueda de caminos de enlace en la red secundaria y función de puntuación multicriterio (`priority_score`).
  - `expansion_planner.py`: Planificador algorítmico territorial de corredores continuos desde ciclovías hacia sectores periféricos desatendidos mediante Reverse Dijkstra y crecimiento voraz por fases (Fase 3.5).
- **Salida:** Archivos en `data/cities/{city_id}/` que cumplen la especificación GeoJSON (RFC 7946).

### 2.2. Repositorio de Datos de Ciudades (`data/cities/`)
Cada ciudad es una unidad autocontenida:
- `city.json`: Metadatos espaciales (centroide, bounding box, zoom inicial), métricas de red, componentes conexas y resumen del plan de expansión territorial.
- `cycling-infrastructure.geojson`: Red de ciclovías existentes (reales).
- `missing-connections.geojson`: Oportunidades de conexión y brechas estructurales prioritarias calculadas algorítmicamente (`is_demo: false`).
- `suggested-routes.geojson`: Rutas amigables para bicicletas calculadas algorítmicamente por vías de bajo tránsito (`is_demo: false`).
- `network-expansion.geojson`: Corredores estructurantes proyectados en fases secuenciales para ampliar la cobertura territorial (`status: ALGORITHMIC_EXPANSION`).

### 2.3. Backend (`backend/`)
- **Framework:** FastAPI en Python 3.12+.
- **Responsabilidad:** Servir metadatos de ciudades, verificar la existencia de capas, proveer endpoints REST tipados bajo Pydantic y ejecutar el **motor de routing determinista (`/api/cities/{city_id}/route`)**.
- **Motor de Routing (`app.routing`):**
  - Carga en memoria el grafo navegable precomputado (`nav_graph.json`).
  - Indexación espacial para snapping de coordenadas ($< 500\text{ m}$).
  - Búsqueda de caminos óptimos mediante algoritmo A* con heurística admisible ($h = \text{haversine} \times 0.70$).
  - Cálculo simultáneo y diferencial contra la ruta físicamente más corta.
  - Caché en memoria y disco (`routes_cache.json`) para respuesta instantánea ($< 10\text{ ms}$).
- **Escalabilidad:** Consumo de memoria controlado (<80MB), sin bases de datos externas requeridas para cómputo de routing.
- **Preparación PostGIS:** La arquitectura está lista para que `data_dir` pueda ser complementado con un conector PostGIS cuando la concurrencia o consultas dinámicas por radio/área lo ameriten.

### 2.4. Frontend (`frontend/`)
- **Stack:** React + TypeScript + Vite + MapLibre GL JS.
- **Componentes Clave:**
  - `MapView`: Renderizado WebGL de capas cartográficas, halos de resalto ámbar para brechas seleccionadas, pines interactivos A y B, y trazado dinámico de rutas y popups enriquecidos.
  - `RoutePlanner`: Tarjeta flotante interactiva para fijar puntos de origen/destino, seleccionar presets urbanos, ejecutar el cálculo y contrastar métricas comparativas.
  - `OpportunitiesList`: Panel lateral interactivo con el ranking de oportunidades de conexión calculadas algorítmicamente, métricas de brecha (`gap_length_m`, `gain_ratio`, `priority_score`), enfoque interactivo (`fitBounds`) y minimización colapsable.
  - `ExpansionPlanCard`: Panel lateral interactivo con el plan maestro de crecimiento territorial secuenciado en fases, métricas agregadas (+km proyectados, +nodos viales, +destinos clave), selección de fases y enfoque en mapa.
  - `LayerControl`: Toggles individuales y control maestro de la capa CicloConecta.
- **Estilo:** Interfaz moderna centrada en el mapa, barra lateral derecha flexible (`.right-sidebar`) que previene solapamientos visuales, controles semitransparentes (glassmorphism), tipografía legible y paleta de colores con alto contraste para accesibilidad.
- **Rendimiento:** Las fuentes de datos se agregan al mapa como `GeoJSONSource` con `LineLayer` optimizadas por hardware (WebGL).

---

## 3. Modelo de Capas y Simbología

| Capa | Identificador | Badge UI | Color | Estilo | Origen y Naturaleza |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ciclovías Existentes** | `cycling-infrastructure` | `OSM` | `#10b981` (Verde Esmeralda) | Línea continua sólida (3.5px) | Infraestructura física mapeada en OpenStreetMap |
| **Conexiones Potenciales** | `missing-connections` | `ALGORÍTMICO` | `#f59e0b` (Ámbar) | Línea discontinua `[4, 2]` (3.5px) | Brechas prioritarias calculadas algorítmicamente sobre red vial OSM |
| **Rutas Sugeridas** | `suggested-routes` | `ALGORÍTMICO` | `#3b82f6` (Azul Ciclista) | Línea continua con halo (3px) | Rutas calculadas algorítmicamente (A*) sobre red vial OSM |
| **Expansión Territorial** | `network-expansion` | `ANÁLISIS` | `#8b5cf6` (Violeta/Morado) | Línea continua con halo morado (3.5px) | Corredores estructurantes proyectados en fases voraces para sectores desatendidos |

---

## 4. Estrategia Multi-Ciudad Declarativa

Desde la **Fase 4**, CicloConecta opera con un modelo completamente desacoplado y guiado por datos:

1. **Registro Declarativo Central (`data/cities/registry.json`)**:
   - Define metadatos territoriales, bounding boxes, presets urbanos y rutas representativas.
2. **Pipeline Unificado (`pipeline/build_city.py`)**:
   - Ejecuta la extracción, construcción de grafos navegables, precomputación de rutas y detección de brechas para cualquier ciudad vía CLI:
     ```bash
     python -m pipeline.build_city --city talca
     ```
3. **Gestión Aislada de Motores (`CityRoutingManager`)**:
   - El backend gestiona un motor independiente por ciudad (`get_city_routing_engine(city_id)`), cargando bajo demanda su grafo $G_{\text{nav}}$ sin bloquear otras ciudades.
4. **Frontend React Adaptativo**:
   - El selector de ciudades en el encabezado consulta `/api/cities` o `registry.json`, sincroniza la URL (`?city=talca`), ajusta los límites del mapa y actualiza la tarjeta de estado (`NetworkStatusCard`) y los accesos rápidos del planificador.
   - Ver guía completa en [`docs/MULTI_CITY.md`](file:///c:/Users/Danich/Documents/Shiroku/ciclovia/docs/MULTI_CITY.md).
