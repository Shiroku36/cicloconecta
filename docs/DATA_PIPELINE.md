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

### Fase 5: Análisis de Conectividad y Detección Algorítmica de Gaps (Fase 3)
1. **Extracción del Subgrafo Ciclista ($G_{\text{cycling}}$):**
   - Se filtran del grafo navegable únicamente aristas con infraestructura ciclista formal (`is_cycleway: true`: ciclovías segregadas, ciclobandas, pistas exclusivas).
   - Se descartan calles ordinarias pedaleables para aislar la red formal protegida.
2. **Descomposición en Componentes Conexas:**
   - Se calculan las componentes débilmente conexas:
     \[
     G_{\text{cycling}} = \{C_1, C_2, \dots, C_k\}
     \]
   - En Curicó se detectaron **31 componentes conexas** que suman 42.22 km. La componente mayor ($C_1$) abarca 19.12 km, seguida por $C_2$ con 4.38 km.
3. **Búsqueda Determinista de Enlaces sobre la Red Vial Real ($G_{\text{nav}}$):**
   - Para cada par de componentes $(C_i, C_j)$, se examinan los nodos terminales y de frontera ($d(u) \le 2$ o nodos de borde).
   - Si la distancia geodésica preliminar es menor a 1,200 m, se calcula la ruta más corta sobre la red vial transitable real $G_{\text{nav}}$ mediante Dijkstra/A*.
   - **Regla estricta:** No se trazan líneas rectas; cada brecha sigue físicamente las calles navegables de la ciudad (evitando cruces imposibles de vías férreas o ríos sin puente).
4. **Función de Priorización Multicriterio (`priority_score`):**
   - Cada oportunidad candidata es evaluada objetivamente en una escala 0–100:
     \[
     S = 0.35 \cdot S_{\text{length}} + 0.30 \cdot S_{\text{network}} + 0.20 \cdot S_{\text{gain}} + 0.15 \cdot S_{\text{stress}}
     \]
     donde:
     * $S_{\text{length}} = \max(0, 100 - (\text{longitud\_m} / 1000) \times 70)$: Premia brechas cortas y de rápida intervención.
     * $S_{\text{network}} = \min(100, (\text{red\_unida\_km} / 25) \times 100)$: Premia conectar componentes grandes o la columna vertebral.
     * $S_{\text{gain}} = \min(100, (\text{gain\_ratio} / 20) \times 100)$: Premia la eficiencia kilométrica unida por metro de intervención.
     * $S_{\text{stress}} \in [0, 100]$: Premia calles secundarias/residenciales tranquilas frente a avenidas de alto tránsito.
5. **Deduplicación y Poda:**
   - Se deduplican conexiones redundantes entre el mismo par de componentes que compartan >60% de alineación espacial, seleccionando la de mayor puntuación.
   - Salida: `missing-connections.geojson` con `is_demo: false` y metadatos exhaustivos por candidato.

### Fase 6: Rutas Sugeridas (Algoritmo A* Determinista — Fase 2)
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

### 4.3. Detección Algorítmica de Conexiones Faltantes (Fase 3)
```bash
python pipeline/build_curico_gaps.py
```
Salida generada:
- `data/cities/curico/missing-connections.geojson` (10 conexiones prioritarias algorítmicas reales, `is_demo: false`)
- `frontend/public/data/cities/curico/missing-connections.geojson` (sincronización estática para visualizador)
- Actualización de métricas de red y componentes conexas en `data/cities/curico/city.json` y `frontend/public/data/cities/curico/city.json`

