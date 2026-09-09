# Guía de Incorporación Multi-Ciudad — CicloConecta

A partir de la **Fase 4**, CicloConecta cuenta con una arquitectura completamente genérica y declarativa. Incorporar una nueva ciudad en Chile **no requiere modificar componentes React, TypeScript ni endpoints de backend**.

El sistema es 100% data-driven: la presencia de una ciudad en el registro central y sus artefactos generados habilitan de forma automática su visualización cartográfica, cálculo de rutas e inspección de brechas.

---

## 1. Arquitectura Multi-Ciudad

El sistema opera bajo un desacoplamiento estricto entre definición, cómputo y consumo:

```text
data/cities/registry.json (Registro Maestro)
       │
       ▼
pipeline.build_city (Pipeline Determinista Unificado)
       │
       ├──> 1. osm_extractor: Ingesta ciclovías Overpass -> cycling-infrastructure.geojson
       ├──> 2. network_extractor: Ingesta red vial Overpass -> nav_graph.json
       ├──> 3. routing precalc: 5 rutas representativas -> suggested-routes.geojson
       └──> 4. gap_detector: Componentes conexas y Top 10 brechas -> missing-connections.geojson
       │
       ▼
data/cities/{city_id}/ + frontend/public/data/cities/{city_id}/
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
Backend FastAPI (vía /api/cities)   Frontend React / Vite (Consumo estático o API)
```

---

## 2. Registro Central de Ciudades (`registry.json`)

El archivo `data/cities/registry.json` (y su réplica idéntica en `frontend/public/data/cities/registry.json`) contiene la lista maestra de ciudades admitidas y configuradas:

```json
{
  "cities": [
    {
      "id": "talca",
      "name": "Talca",
      "province": "Talca",
      "region": "Región del Maule",
      "country": "Chile",
      "enabled": true,
      "center": [-71.6554, -35.4264],
      "initial_zoom": 13.5,
      "bounds": [[-71.695, -35.465], [-71.605, -35.395]],
      "bbox": [-35.465, -71.695, -35.395, -71.605],
      "description": "Red ciclista y análisis de conectividad urbana para Talca, Región del Maule.",
      "presets": [
        { "id": "talca-01", "name": "Plaza de Armas (Centro)", "coord": [-71.6663, -35.4261] },
        { "id": "talca-02", "name": "Campus Lircay UTalca (Norte)", "coord": [-71.636, -35.4045] }
      ],
      "representative_routes": [
        {
          "name": "Campus UTalca Lircay a Plaza de Armas",
          "origin": [-71.636, -35.4045],
          "destination": [-71.6663, -35.4261]
        }
      ]
    }
  ]
}
```

### Campos requeridos
* `id`: Identificador alfanumérico en minúsculas (ej: `curico`, `talca`, `rancagua`).
* `name`, `province`, `region`, `country`: Toponimia formal chilena.
* `enabled`: Booleano. Si es `false`, aparece en la interfaz con badge "Próximamente" sin intentar cargar capas inexistentes.
* `center`: `[longitud, latitud]` del centro urbano.
* `initial_zoom`: Nivel de acercamiento inicial (típicamente 13.0 a 14.0).
* `bounds`: `[[lon_min, lat_min], [lon_max, lat_max]]` para acotar la cámara MapLibre.
* `bbox`: `[lat_min, lon_min, lat_max, lon_max]` usado para consultas Overpass OSM.
* `presets`: Puntos de interés comunes (hitos urbanos, universidades, hospitales, terminales).
* `representative_routes`: Al menos 5 pares origen/destino reales para la capa inicial de rutas sugeridas.

---

## 3. Ejecución del Pipeline Unificado

Para procesar una ciudad completa desde cero:

```bash
# Procesar una ciudad específica
python -m pipeline.build_city --city talca

# Forzar recarga completa desde OpenStreetMap ignorando cachés locales
python -m pipeline.build_city --city talca --refresh

# Procesar todas las ciudades que tengan enabled: true en registry.json
python -m pipeline.build_city --all-enabled
```

### ¿Qué hace el pipeline internamente?
1. **Verificación de BBox y Registro**: Lee la configuración de la ciudad desde `registry.json`.
2. **Descarga y Clasificación de Ciclovías**:
   - Consulta Overpass con endpoints redundantes (`overpass-api.de`, `kumi.systems`, `private.coffee`).
   - Normaliza la infraestructura ciclista bajo estándar CicloConecta (`segregated`, `on_street`, `shared_busway`, etc.).
   - Guarda `data/cities/{city_id}/cycling-infrastructure.geojson`.
3. **Construcción del Grafo Vial Navegable**:
   - Descarga todas las vías ciclables de la ciudad (calles residenciales, secundarias, terciarias, ciclovías).
   - Genera topología $G_{\text{nav}}$ en NetworkX y serializa `nav_graph.json` con índice de nodos.
4. **Precomputación de Rutas Sugeridas**:
   - Calcula con algoritmo A* determinista las rutas para los pares de `representative_routes`.
   - Asigna métricas de longitud total y porcentaje de infraestructura segura.
   - Exporta `data/cities/{city_id}/suggested-routes.geojson`.
5. **Detección Algorítmica de Brechas (Top 10 Gaps)**:
   - Descompone la red ciclista en componentes conexas independientes.
   - Evalúa candidatos conectores sobre el grafo vial navegable respetando sentidos de circulación y continuidad física.
   - Aplica índice multicriterio de prioridad (0-100 pts) considerando ganancia de conectividad, compacidad y seguridad vial.
   - Exporta `data/cities/{city_id}/missing-connections.geojson`.
6. **Consolidación de Métricas y Sincronización Web**:
   - Actualiza `city.json` con estadísticas de kilómetros, tramos y componentes.
   - Copia atómicamente todos los artefactos a `frontend/public/data/cities/{city_id}/` para garantizar funcionamiento estático sin servidor backend activo.

---

## 4. Resiliencia y Control de Artefactos Pesados

### Exclusión en Git (`.gitignore`)
Las respuestas crudas de Overpass (`raw_network.json`, `raw_cycleways.json`) y cachés volátiles (`routes_cache.json`) superan decenas de megabytes y cambian frecuentemente. Están excluidas del repositorio Git:

```gitignore
data/cities/*/raw_network.json
data/cities/*/raw_cycleways.json
data/cities/*/routes_cache.json
```

Por el contrario, los artefactos procesados:
* `city.json`
* `cycling-infrastructure.geojson`
* `missing-connections.geojson`
* `suggested-routes.geojson`
* `nav_graph.json` (para ciudades habilitadas)

**Sí se versionan en Git**, garantizando que el entorno de producción, la suite de tests en CI y el visualizador web funcionen de inmediato sin depender de APIs de terceros en tiempo de despliegue.

---

## 5. Aislamiento en el Backend

El módulo `backend/app/routing/manager.py` administra los motores de routing de cada ciudad de forma totalmente independiente:

* Cada ciudad posee su propia instancia de `RoutingEngine` con su grafo $G_{\text{nav}}$ en memoria.
* Una consulta en Talca no interfiere ni bloquea consultas en Curicó.
* Carga perezosa (*lazy loading*): el grafo de una ciudad solo se carga en RAM cuando recibe su primera solicitud de ruta, ahorrando memoria en arranque.

---

## 6. Paso a Paso: Agregar una Nueva Ciudad (Ejemplo: Rancagua)

1. Abrir `data/cities/registry.json`.
2. Definir los parámetros geográficos de Rancagua:
   - `id`: `"rancagua"`
   - `bbox`: `[-34.205, -70.785, -34.135, -70.705]`
   - `center`: `[-70.740, -34.170]`
   - `presets`: Plaza de Los Héroes, Hospital Regional, UOH Campus Rancagua, etc.
   - `representative_routes`: 5 pares de origen/destino.
   - Cambiar `"enabled": true`.
3. Ejecutar el pipeline de construcción:
   ```bash
   python -m pipeline.build_city --city rancagua
   ```
4. Ejecutar la suite de pruebas:
   ```bash
   python -m pytest backend/tests
   ```
5. ¡Listo! El selector del frontend mostrará inmediatamente Rancagua con sus ciclovías, rutas sugeridas, análisis de componentes y planificador activo.
