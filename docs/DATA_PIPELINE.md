# Especificación del Pipeline de Datos Geoespaciales — CicloConecta

Este documento describe la arquitectura técnica, los principios matemáticos y la implementación determinista del pipeline de datos de CicloConecta, diseñado para extraer redes ciclistas, normalizar topologías, analizar conectividad y detectar brechas (gaps) urbanas.

---

## 1. Principio Fundamental: Algoritmos Deterministas vs IA

> [!IMPORTANT]
> **Regla de Diseño del Pipeline:**
> No se utilizan modelos de lenguaje (LLMs) ni aproximaciones estocásticas para operaciones que corresponden a algoritmos espaciales deterministas.
> - **Deterministas (Algoritmos):** Grafo vial, rutas mínimas (Dijkstra / A*), componentes conexas, distancias geodésicas, intersecciones geométricas, buffers espaciales.
> - **IA Generativa (Futuro):** Explicación narrativa de resultados para la comunidad, redacción de minutas para municipios, priorización contextual basada en texto de ordenanzas comunales.

---

## 2. Fases del Pipeline

```text
       [ 1. Ingesta OSM ]
   Overpass API / Geofabrik PBF
              │
              ▼
    [ 2. Filtrado y Tipificación ]
  highway=cycleway / cycleway=*
              │
              ▼
    [ 3. Limpieza Topológica ]
  Snap to vertex / Segmentación
              │
              ▼
    [ 4. Modelado en Grafo ]
      G = (V, E) con pesos
              │
              ▼
   [ 5. Detección de Discontinuidades ]
 Componentes inconexas / Dead-ends
              │
              ▼
   [ 6. Simulación de Conectores ]
 Búsqueda en red vial de baja velocidad
              │
              ▼
    [ 7. Exportación Estandarizada ]
 GeoJSON normalizado + city.json
```

---

## 3. Detalle de Implementación por Fase

### Fase 1: Ingesta de Red Vial Abierta
- **Fuente primaria:** OpenStreetMap vía Overpass API (o archivos `.osm.pbf` procesados con `osmium` para regiones enteras).
- **Parámetros de entrada:** Bounding box (`south, west, north, east`) o código de relación administrativa de la comuna (ej. Curicó: `relation["admin_level"="8"]["name"="Curicó"]`).
- **Tags consultados:**
  - `highway=cycleway` (ciclovía segregada física)
  - `cycleway=lane` / `cycleway=track` / `cycleway:both=*` (ciclobanda demarcada en calzada)
  - `bicycle=designated` (vía formalmente destinada a bicicletas)
  - Red vial adyacente: `highway in (residential, living_street, tertiary, secondary, primary)` para análisis de contexto.

### Fase 2: Normalización y Atributos
Cada segmento vial extraído es enriquecido y normalizado en un esquema estándar:
- `id`: Identificador canónico único (`{city_id}-osm-{way_id}`).
- `name`: Nombre de la vía o avenida (ej. "Avenida Bernardo O'Higgins").
- `type`: Clasificación semántica (`Pista exclusiva segregada`, `Ciclocalle demarcada`, `Vía de uso preferente`).
- `surface`: Materialidad de rodadura (`asphalt`, `paved`, `concrete`, etc.).
- `length_m`: Longitud exacta calculada por la fórmula geodésica del semiverseno (Haversine) o elipsoide WGS84.
- `source`: Atribución legal (`OpenStreetMap Contributors`).
- `is_demo`: Bandera booleana estricta (`false` para datos reales verificados).

### Fase 3 & 4: Construcción del Grafo Vial (NetworkX / OSMnx)
1. Los nodos OSM que comparten coordenadas coincidentes son indexados como vértices \(V\).
2. Los tramos (`ways`) representan aristas ponderadas \(E\) con pesos calculados como:
   \[
   W(e) = \text{longitud}(e) \times C_{\text{estrés}}(e)
   \]
   donde \(C_{\text{estrés}}\) pondera la seguridad de la vía (menor estrés para ciclovía física, mayor para calzadas sin segregar).

### Fase 5: Análisis de Conectividad y Gaps (Brechas)
1. **Componentes Conexas:** Se identifican los subgrafos desconectados de la red ciclista:
   \[
   G_c = \{C_1, C_2, \dots, C_k\}
   \]
2. **Identificación de Puntas Abiertas (Dead-ends):** Nodos con grado \(d(v) = 1\) dentro de la red ciclista que se ubican a menos de \(D_{\text{umbral}}\) (ej. 300 - 800 metros) de otra ciclovía pero obligan al ciclista a descender o circular por autopistas peligrosas.
3. **Cálculo de Conexiones Prioritarias:** Se ejecuta una búsqueda de camino más corto en la red vial secundaria para unir \(C_i\) con \(C_j\), generando la capa de `missing-connections.geojson`.

### Fase 6: Rutas Sugeridas (Algoritmo A* Determinista — Implementado en Fase 2)
- Reemplazo completo de rutas DEMO por rutas algorítmicas calculadas sobre la red vial real de OpenStreetMap.
- Costo ponderado por infraestructura ciclista ($\text{costo} = \text{distancia} \times \text{penalización}$).
- Heurística admisible $h(u, v) = \text{haversine}(u, v) \times 0.70$.
- Comparación automática contra la ruta física más corta en distancia.
- Salida: `suggested-routes.geojson` con `is_demo: false` y métricas de comparación.

### Fase 7: Exportación a Contratos de Visualización
- Los resultados se exportan como GeoJSON FeatureCollections estáticos directamente consumibles por el visualizador MapLibre, y como grafo serializado `nav_graph.json` consumible por la API REST de FastAPI para consultas interactivas instantáneas.

---

## 4. Ejecución del Pipeline para Curicó

### 4.1. Extracción de Infraestructura Ciclista Existente (Fase 1)
```bash
python pipeline/osm_extractor.py
```
Salida generada:
- `data/cities/curico/cycling-infrastructure.geojson` (121 tramos reales, 43.2 km)
- `data/cities/curico/city.json`

### 4.2. Construcción del Grafo Vial y Routing Algorítmico (Fase 2)
```bash
python pipeline/build_curico_routing.py
```
Salida generada:
- `data/cities/curico/nav_graph.json` (Grafo conectado: 16,252 nodos, 33,545 aristas)
- `data/cities/curico/suggested-routes.geojson` (5 rutas representativas reales calculadas algorítmicamente)
- Sincronización automática de `suggested-routes.geojson` a `frontend/public/data/cities/curico/`

