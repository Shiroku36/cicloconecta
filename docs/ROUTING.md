# CicloConecta — Motor de Routing Ciclista Determinista

## 1. Principio y Filosofía del Routing Ciclista

En la planificación ciclista urbana, la **ruta más corta en distancia física no suele ser la ruta óptima para una persona en bicicleta**.

Una ruta puramente física más corta suele obligar al ciclista a compartir calzadas con alto tráfico vehicular motorizado, velocidades elevadas (50–60 km/h) y múltiples pistas, aumentando exponencialmente el estrés y la probabilidad de siniestros viales.

CicloConecta implementa un **motor de routing determinista** basado en la red vial real de **OpenStreetMap (OSM)** que penaliza el tráfico hostil y premia la infraestructura ciclista protegida y las calles calmas:

$$\text{costo} = \text{distancia\_metros} \times \text{factor\_penalización}$$

Donde:
* Un **menor factor de penalización** incentiva al algoritmo a preferir esa vía.
* Un **factor de penalización elevado** desincentiva el paso salvo que sea indispensable para conectar.
* Vías prohibidas (autopistas, `access=no`, `bicycle=no`) tienen penalización $\infty$ y son completamente excluidas del grafo.

---

## 2. Tabla de Factores de Penalización

| Categoría de Vía | Etiquetas OSM | Factor de Penalización | Justificación |
| :--- | :--- | :---: | :--- |
| **Ciclovía segregada protegida** | `highway=cycleway` + `segregated=yes`, `cycleway=track` | **0.70** | Máxima protección física y prioridad ciclista. |
| **Ciclovía dedicada** | `highway=cycleway`, `cycleway:left/right=track` | **0.78** | Vía exclusiva para bicicletas. |
| **Ciclobanda demarcada** | `cycleway=lane`, `cycleway:left/right=lane` | **0.88** | Espacio delimitado en calzada vehicular. |
| **Calle residencial calma (30 km/h)** | `highway=living_street` o `maxspeed <= 30` | **0.95** | Velocidad reducida, bajo volumen vehicular. |
| **Calle residencial estándar** | `highway=residential` | **1.05** | Tráfico barrial habitual. |
| **Vía de servicio / Pasaje** | `highway=service`, `highway=unclassified` | **1.10 – 1.15** | Tráfico local lento. |
| **Vía colectora terciaria** | `highway=tertiary` | **1.45** | Flujo vehicular moderado a alto. |
| **Arteria secundaria** | `highway=secondary` | **1.90** | Alto flujo motorizado, transporte público. |
| **Arteria primaria principal** | `highway=primary` | **2.60** | Vía rápida peligrosa sin ciclovía. |
| **Vía rápida / Troncal urbana** | `highway=trunk` | **3.80** | Tránsito pesado interurbano; solo si no hay alternativa. |
| **Autopista / Acceso prohibido** | `highway=motorway`, `bicycle=no` | **$\infty$ (Bloqueado)** | Prohibición legal o física para bicicletas. |

### Ajustes Dinámicos Adicionales
* **Límite de velocidad (`maxspeed`)**:
  * $\le 30\text{ km/h}$: bonificación de $-10\%$ en costo.
  * $\ge 50\text{ km/h}$: penalización $+0.20$.
  * $\ge 60\text{ km/h}$: penalización $+0.40$.
* **Número de pistas (`lanes`)**:
  * $\ge 3$ pistas: penalización $+0.25$.
  * $\ge 4$ pistas: penalización $+0.50$.
* **Superficie rugosa (`surface=unpaved|gravel|dirt`)**:
  * Penalización $+0.35$ por rodado deficiente.

---

## 3. Sentido del Tránsito y Excepciones para Bicicletas

El motor evalúa rigurosamente la dirección permitida:
* **Sentido único vehicular (`oneway=yes`)**: Por defecto restringe el sentido opuesto.
* **Excepción explícita (`oneway:bicycle=no`)**: Permite bidireccionalidad ciclista aun cuando los automóviles tengan sentido único.
* **Ciclovías a contraflujo (`cycleway=opposite_lane|opposite_track`)**: Permiten circulación inversa segura y legal.

---

## 4. Ajuste Espacial a la Red (Spatial Snapping)

Las coordenadas de origen y destino solicitadas por el usuario o por preset se ajustan al nodo navegable más cercano mediante `SpatialNodeIndex`:
1. Indexación en cuadrícula espacial en memoria ($O(1)$ promedio por celda).
2. Cálculo de distancia geodésica (Haversine).
3. **Umbral de seguridad**: Si el punto está a más de 500 metros de cualquier vía navegable, la consulta retorna un error `400 Bad Request` explicando que el punto está fuera de la red urbana.

---

## 5. Algoritmo de Búsqueda A* y Admisibilidad

El cálculo utiliza el algoritmo **A*** sobre un grafo dirigido `NetworkX`:
* Para asegurar la optimalidad matemática sin sobrestimar el costo real (admisibilidad y consistencia monotónica), la heurística entre un nodo $u$ y la meta $v$ es:

$$h(u, v) = \text{haversine}(u, v) \times 0.70$$

Dado que $0.70$ es el factor de penalización mínimo absoluto en el sistema (ciclovías segregadas), la función heurística nunca sobrestima el costo real de ningún camino, garantizando la ruta óptima en milisegundos ($< 15\text{ ms}$ en Curicó).

---

## 6. Las 5 Rutas Representativas de Curicó

Se calcularon 5 corredores urbanos reales en Curicó, comparando la **Ruta Ciclista Optimizada** contra la **Ruta Más Corta Vehicular**:

| Corredor | Origen $\rightarrow$ Destino | Distancia Ciclista | % Ciclovía | Distancia Más Corta | % Ciclovía Corta | Ganancia Ciclovía | Desvío Necesario |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Ruta Norte** | Rauquén (Av. Rauquén) $\rightarrow$ Plaza de Armas | **4.39 km** | **52.9%** | 4.20 km | 20.0% | **+32.9%** | +190 m (+4.4%) |
| **2. Ruta Oriente** | Zapallar / El Boldo $\rightarrow$ Plaza de Armas | **4.23 km** | **70.8%** | 2.97 km | 14.7% | **+56.1%** | +1.26 km (+42.6%) |
| **3. Ruta Poniente** | Santa Fe / Alessandri $\rightarrow$ Plaza de Armas | **2.58 km** | **16.2%** | 2.42 km | 0.0% | **+16.2%** | +160 m (+6.7%) |
| **4. Circuito Universitario** | Campus UTalca / Los Niches $\rightarrow$ Plaza de Armas | **2.39 km** | **46.7%** | 2.30 km | 0.0% | **+46.7%** | +90 m (+3.7%) |
| **5. Eje Intermodal** | Guaiquillo Sur $\rightarrow$ Estación Trenes (EFE) | **4.08 km** | **42.3%** | 3.63 km | 4.7% | **+37.6%** | +450 m (+12.4%) |

### Observaciones Clave:
* En la **Ruta Norte**, un pequeño desvío de solo 190 metros (4.4%) permite realizar más de la mitad del recorrido (52.9%) por ciclovías segregadas.
* En el **Circuito Universitario**, un desvío insignificante de 90 metros aumenta la infraestructura segura de 0% a casi la mitad del trayecto (46.7%).
* En el **Eje Intermodal**, el ciclista evita avenidas colapsadas de alta velocidad tomando el eje cicloviario, reduciendo el score de estrés de 5,668 a 3,694 puntos.

---

## 7. API REST: `POST /api/cities/{city_id}/route`

### Request
```json
{
  "origin": [-71.2185, -34.9620],
  "destination": [-71.2394, -34.9854],
  "max_snap_dist_m": 600.0
}
```

### Response
```json
{
  "city_id": "curico",
  "origin": {
    "requested": [-71.2185, -34.9620],
    "snapped_node": 1234567,
    "snap_distance_m": 12.4
  },
  "destination": {
    "requested": [-71.2394, -34.9854],
    "snapped_node": 9876543,
    "snap_distance_m": 8.1
  },
  "cycling_route": {
    "distance_km": 4.39,
    "distance_m": 4390.2,
    "cycling_infra_km": 2.32,
    "cycling_infra_pct": 52.9,
    "cost_score": 4236.5,
    "streets": ["Pasaje 1", "Caen", "El Peumo", "Av. Manso de Velasco", "Carmen"],
    "coordinates": [[-71.218662, -34.961926], ...]
  },
  "shortest_route": {
    "distance_km": 4.20,
    "distance_m": 4201.8,
    "cycling_infra_km": 0.84,
    "cycling_infra_pct": 20.0,
    "cost_score": 6106.8,
    "streets": [...],
    "coordinates": [[-71.218662, -34.961926], ...]
  },
  "comparison": {
    "distance_diff_km": 0.19,
    "length_diff_pct": 4.4,
    "cycling_gain_pct": 32.9,
    "is_same_path": false
  },
  "cached": false
}
```
