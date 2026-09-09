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
- **Filosofía Algorítmica:** Algoritmos matemáticos y de teoría de grafos deterministas para calcular distancias, conectividad de componentes y rutas más cortas. No se utilizan modelos de lenguaje para cálculos espaciales.
- **Salida:** Archivos en `data/cities/{city_id}/` que cumplen la especificación GeoJSON (RFC 7946).

### 2.2. Repositorio de Datos de Ciudades (`data/cities/`)
Cada ciudad es una unidad autocontenida:
- `city.json`: Metadatos espaciales (centroide, bounding box, zoom inicial), descripción y métricas agregadas (km totales, fecha de actualización).
- `cycling-infrastructure.geojson`: Red de ciclovías existentes (reales).
- `missing-connections.geojson`: Tramos discontinuos o desconexiones críticas entre ejes.
- `suggested-routes.geojson`: Rutas amigables para bicicletas por vías de bajo tránsito.

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
  - `MapView`: Renderizado WebGL de capas cartográficas, pines interactivos A y B, y trazado dinámico de ruta activa y ruta más corta alternativa.
  - `RoutePlanner`: Tarjeta flotante interactiva para fijar puntos de origen/destino, seleccionar presets urbanos, ejecutar el cálculo y contrastar métricas comparativas.
  - `LayerControl`: Toggles individuales y control maestro de la capa CicloConecta.
- **Estilo:** Interfaz moderna centrada en el mapa, controles flotantes semitransparentes (glassmorphism), tipografía legible y paleta de colores con alto contraste para accesibilidad.
- **Rendimiento:** Las fuentes de datos se agregan al mapa como `GeoJSONSource` con `LineLayer` optimizadas por hardware (WebGL).

---

## 3. Modelo de Capas y Simbología

| Capa | Identificador | Color | Estilo | Origen de Datos |
| :--- | :--- | :--- | :--- | :--- |
| **Ciclovías Existentes** | `cycling-infrastructure` | `#10b981` (Verde Esmeralda) | Línea continua sólida (3.5px) | OpenStreetMap (Reales) |
| **Conexiones Faltantes** | `missing-connections` | `#f59e0b` (Ámbar) | Línea discontinua `[3, 2]` (3px) | Algoritmo de Gaps / DEMO |
| **Rutas Sugeridas** | `suggested-routes` | `#3b82f6` (Azul Ciclista) | Línea continua con halo (3px) | Routing A* sobre red vial OSM (Reales) |

---

## 4. Estrategia Multi-Ciudad

El sistema fue diseñado desde el inicio para evitar que agregar una ciudad (`talca`, `santiago`, etc.) requiera cambios en el código del visor:
1. Se crea la carpeta `data/cities/{nombre_slug}/`.
2. Se ejecuta el pipeline especificando el bounding box y centroide de la comuna.
3. El backend expone la nueva ciudad en `/api/cities`.
4. El frontend carga la lista de ciudades disponibles en el selector y vuela la cámara (`map.flyTo`) a las nuevas coordenadas.
