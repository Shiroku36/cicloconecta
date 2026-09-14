# Bitácora de Progreso — CicloConecta

Este documento actúa como la **fuente de verdad del desarrollo** entre agentes y colaboradores, registrando de forma cronológica y estructurada los avances, validaciones, problemas resueltos y temas pendientes del proyecto.

---

## [2026-09-14] — Fase 3.6: Crecimiento Topológico Real de la Red (Red Activa Dinámica, Tipología y Dependencias)

### 1. ¿Qué se implementó y corrigió?
- **Crecimiento Topológico Real con `ActiveCyclingNetwork`:**
  - Se implementó la clase `ActiveCyclingNetwork` en `pipeline/expansion_planner.py`, modelando la acumulación progresiva de la red ciclista (base OSM + fases aprobadas precedentes).
  - Se corrigió el déficit conceptual de la Fase 3.5 donde los candidatos se generaban una sola vez desde la red base; ahora, en cada iteración $k$, los corredores se trazan dinámicamente conectando hacia toda la red activa disponible en ese momento.
- **Detección Dinámica de Nodos Desatendidos y Clusters Activos:**
  - En cada fase, se recalculan los nodos de acceso desatendidos ($> 400\text{ m}$ de la red activa) y se actualizan los clusters territoriales vigentes, asegurando que las nuevas fases atiendan la demanda residual real.
- **Tipología de Expansión y Dependencias Topológicas Explícitas:**
  - Clasificación determinista de cada propuesta en `trunk_extension`, `continuation`, `branch` o `cross_connector`.
  - Detección precisa de los nodos de contacto con la red activa y almacenamiento de identificadores de fases previas requeridas en `depends_on` (garantizando $j < k$).
- **Puntuación de Continuidad Dinámica ($S_{\text{cont}} \in [8.0, 20.0]$):**
  - Eliminada la constante fija de $20.0$ pts. Se bonifican extensiones troncales directas (+4.0), conexiones a la red dorsal principal (> 5 km, +3.0) y cierres de bucles (+3.0), penalizando trazados predominantemente rurales sin servicios (-3.0).
- **Clasificación de Contexto Territorial (Urbano vs. Periurbano):**
  - Incorporados campos `urban_context` (`urban`, `periurban`, `uncertain`) y `environment_label` ("Expansión Urbana", "Conector Periurbano", "Mixto / Transición") basados en proporción de vías no urbanizadas (`track`, `unclassified`), densidad de POIs a 400 m y trama residencial consolidada.
- **Eliminación Total de Código de Depuración:**
  - `get_debug_manual_anchors()` completamente suprimido del código de producción.
- **Validación Comparativa A/B en Curicó:**
  - Modelo A (Estático): 7.84 km, 1.142 nodos, 50 POIs, 145.7 nodos/km, 6 ramas aisladas (efecto estrella), Fase 6 en Ruta J-624 (2.61 km rural).
  - Modelo B (Crecimiento Topológico): 6.83 km (-13% asfalto), 1.097 nodos, 55 POIs (+10% servicios), 160.6 nodos/km (+10.2% eficiencia). Fase 6 es una `continuation` que prolonga la Fase 2 (Callejón San José) en 1.52 km hasta la Escuela María Olga Figueroa Leyton, formando un eje estructurante continuo de 3.05 km.
- **Validación en Talca:**
  - 6 fases (+5.81 km, +2.091 nodos, +76 POIs). Fase 4 es un `trunk_extension` que prolonga la Fase 3 sobre Calle 27/34 Oriente (`depends_on: ['expansion-talca-03']`).
- **Frontend y Visualización:**
  - Actualizado `ExpansionPlanCard.tsx` con badges de tipología, entorno y dependencias (`🔗 Requiere Fase X`).
  - Actualizado `MapView.tsx` con popup detallado que incluye tipo de expansión, contexto territorial, eje estructurante y dependencias.
- **Suite de Pruebas:**
  - 7 nuevos tests unitarios en `backend/tests/test_expansion.py` validando crecimiento de la red activa, dependencias estrictas, tipologías válidas y variación de $S_{\text{cont}}$.
  - **47 de 47 tests pasando en 1.95s**.
  - Oxlint: **0 errores, 0 advertencias**. Vite build: **Exitoso**.

---

## [2026-09-14] — Fase 3.5 (Corrección Metodológica): Descubrimiento Territorial Inductivo, Clustering DBSCAN y Validación en Curicó y Talca

### 1. ¿Qué se implementó y corrigió?
- **Saneamiento del Repositorio:**
  - Eliminado documento ajeno `docs/VALIDACION-PC-CORPORATIVO.md` mediante commit estándar `088bfcd` sin alterar el historial.
- **Eliminación Total de Anclas Manuales:**
  - Suprimida la función `get_city_anchors()` y cualquier condicional hardcodeado por ciudad en `pipeline/expansion_planner.py`.
  - El algoritmo de expansión opera ahora de forma 100% inductiva a partir de datos cartográficos de OpenStreetMap.
- **Deduplicación Espacial de POIs:**
  - Implementada regla de proximidad estricta ($< 15\text{ m}$ absoluto) y similitud de categoría/nombre ($< 150\text{ m}$).
  - *Curicó:* 592 POIs brutos $\to$ 551 POIs únicos consolidados.
  - *Talca:* 982 POIs brutos $\to$ 905 POIs únicos consolidados.
- **Bandas de Distancia y Métricas de Acceso Urbano:**
  - Categorización explícita de nodos de acceso urbano en bandas: $0–250\text{ m}$, $250–500\text{ m}$, $500–1000\text{ m}$, $>1000\text{ m}$.
  - Nodos a $> 400\text{ m}$ considerados desatendidos (4.001 en Curicó, 6.262 en Talca). Prohibición estricta de afirmar "población/habitantes beneficiados".
- **Descubrimiento Algorítmico de Clusters (DBSCAN Determinista):**
  - DBSCAN con $\varepsilon = 300\text{ m}$ y $\text{min\_samples} = 20$.
  - Descubrimiento de 28 clusters en Curicó y 21 clusters en Talca.
  - Selección automatizada del ancla óptima por densidad local, cercanía a POIs y centralidad.
- **Generación Multi-Alternativa de Corredores y Jerarquía Estructurante:**
  - Generación de alternativas Directa y Eje Estructurante por cluster, filtrando trazados de $500\text{ m}$ a $3.500\text{ m}$ con sinuosidad $\le 1.35$.
  - Reemplazo de aptitud vial por `structural_axis_score` ($5.0 - 10.0$ pts) basado en jerarquía arterial (`secondary`, `tertiary`) sin emitir juicios no verificados sobre perfil o ancho de vía.
- **Plan Maestro Curicó:**
  - 6 fases (+7.84 km de red proyectada, +1.181 nodos de acceso urbano ganados, +50 POIs únicos).
  - Sectores priorizados: Mataquito (0.90 km, 95.0 pts), Callejón San José / Rauquén Norte (1.53 km, 94.0 pts), Nazareth / Salcobrand (0.92 km, 80.8 pts), Nueva América (0.73 km, 75.4 pts).
- **Generalización Exitosa en Talca:**
  - 6 fases (+5.72 km de red proyectada, +2.126 nodos de acceso urbano ganados, +78 POIs únicos).
  - Sectores priorizados: 14 Sur (0.83 km, 99.6 pts), 26 Sur / La Florida (1.86 km, 98.8 pts), Calle 27 Oriente (0.78 km, 97.4 pts), Calle 34 Oriente (0.89 km, 95.9 pts).
- **Suite de Pruebas Unitarias y de Integración:**
  - 11 nuevos tests en `backend/tests/test_expansion.py` validando ausencia de anclas hardcodeadas, consistencia de deduplicación de POIs, detección de clusters $>400\text{ m}$, endpoints GeoJSON de ambas ciudades, ordenamiento monótono de fases y ausencia de claims no verificados.
  - **42 de 42 tests pasando en 1.40s**.
- **Frontend y Linter:**
  - Oxlint: **0 errores, 0 advertencias** en 13 archivos.
  - Build de Vite: **Exitoso**.
  - Verificación visual CDP headless: Capturas generadas confirmando visualización de las 4 capas (`OSM`, `ALGORÍTMICO`, `ALGORÍTMICO`, `ANÁLISIS`) y selección interactiva de fases en Curicó y Talca.

---

## [2026-09-11] — Fase 3.5: Planificador Algorítmico de Expansión de Red Territorial (Curicó)

### 1. ¿Qué se implementó?
- **Distinción Estructural de Planificación:**
  - Se mantuvo 100% activa e independiente la capa de **Conexiones potenciales** (`missing-connections`, badge `ALGORÍTMICO`, `#b45309`, 10 brechas cortas entre componentes inconexas).
  - Se creó la nueva capa **Expansión de red** (`network-expansion`, badge `ANÁLISIS`, `#8b5cf6`, corredores estructurantes de 500 m a 3.5 km hacia sectores desatendidos).
- **Proxy de Cobertura Urbana sin Inventar Población:**
  - Prohibición estricta de afirmar "habitantes beneficiados" sin censo a nivel predial.
  - Modelo objetivo fundamentado en:
    * Grafo de nodos viales residenciales ($V_{\text{res}}$): 16.252 nodos viales de calles `residential`, `living_street`, `service`, `unclassified`.
    * Equipamientos y POIs verificados de OSM ($P_{\text{poi}}$): 592 puntos esenciales (educación, salud, comercio, recreación).
    * Radio de cobertura caminable/pedaleable local: $R_{\text{cov}} = 400\text{ m}$.
  - Cobertura base inicial en Curicó: 69.5% de nodos residenciales y 78.7% de equipamientos cubiertos.
- **Trazado Determinista de Corredores (Reverse Dijkstra Óptimo):**
  - Implementación en `pipeline/expansion_planner.py`: Dijkstra inverso desde el polo habitacional hacia la red de ciclovías existente.
  - Función de costo penalizando vías rápidas y favoreciendo avenidas colectoras.
  - Filtro geométrico con ratio de sinuosidad $\le 1.30$ (ratios reales entre 1.09 y 1.20).
- **Función de Puntuación Multicriterio ($0 - 100\text{ pts}$):**
  - Ganancia de nodos residenciales (35 pts), POIs nuevos (25 pts), Continuidad con red base (20 pts), Jerarquía vial (10 pts) y Eficiencia territorial $\Delta N / \text{km}$ (10 pts).
- **Crecimiento Voraz por Fases (Greedy Iterative Expansion):**
  - Plan maestro de 6 fases secuenciales en Curicó (+5.59 km proyectados, +813 nodos residenciales ganados a $\le 400\text{ m}$, +56 POIs incorporados):
    1. **Fase 1 (Score 91.7):** Eje Norte: Av. Rauquén Norte → Don Sebastián / Los Héroes (1.21 km, +229 nodos, +12 POIs).
    2. **Fase 2 (Score 89.0):** Eje Surponiente: Mataquito → Villa Mejillones / Santos Martínez (0.89 km, +206 nodos, +23 POIs).
    3. **Fase 3 (Score 80.8):** Eje Oriente: Av. Zapallar Oriente (0.89 km, +122 nodos, +6 POIs).
    4. **Fase 4 (Score 79.6):** Eje Poniente: Santa Fe → Trapiche Poniente (0.77 km, +117 nodos, +11 POIs).
    5. **Fase 5 (Score 74.1):** Eje Norponiente: Tutuquén Poniente (0.89 km, +87 nodos, +4 POIs).
    6. **Fase 6 (Score 70.0):** Eje Norte Exterior: Conexión Sarmiento (0.94 km, +52 nodos, +0 POIs).
- **Integración en el Pipeline (`pipeline/build_city.py`):**
  - Incorporado como paso `[5/7]`, ejecutándose en 1.6 segundos con sincronización hacia `frontend/public/data/cities/curico/network-expansion.geojson`.
- **Backend API (`backend/app/` y `backend/tests/`):**
  - Capa registrada en `LAYER_DEFINITIONS` (`#8b5cf6`, `is_demo: false`, badge `ANÁLISIS`).
  - Esquema Pydantic `CitySummary` con campo `expansion` opcional.
  - Suite de tests unitarios completa (`backend/tests/test_expansion.py`): **35 de 35 tests pasando en 1.24s**.
- **Frontend Interactivo (React + TypeScript + MapLibre):**
  - Componente `ExpansionPlanCard.tsx` con resumen (+5.6 km, +813 nodos, +56 POIs), selección interactiva de fases y activación automática de capa.
  - MapView: halo de selección morado (`casing-selected-expansion` y `line-selected-expansion`), `fitBounds` dinámico al seleccionar una fase y popup enriquecido con badge `PROPUESTA DE EXPANSIÓN (ANÁLISIS)`, fase, score, longitud, nodos, POIs y disclaimer legal.
  - Linter: **0 errores, 0 advertencias** (`oxlint`). Build de producción: **Exitoso** (`vite build`).

### 2. ¿Qué se comprobó visualmente en ejecución?
- Verificación automatizada vía Chrome CDP headless:
  - **`phase3_5_01_all_layers.png`:** Visualización simultánea y sin colisiones de las 4 capas activas en Curicó (verde ciclovías, ámbar brechas, azul rutas, morado expansión territorial).
  - **`phase3_5_02_expansion_popup.png`:** Selección de la Fase 1 (Av. Rauquén Norte), zoom automático con `fitBounds`, halo morado activo, tarjeta seleccionada y popup completo con todos sus atributos y disclaimer.
  - **`phase3_5_03_fase2_popup.png`:** Selección interactiva de la Fase 2 (Mataquito / Villa Mejillones), vuelo de cámara hacia el surponiente, halo activo y popup con desglose de +206 nodos y +23 POIs.

---

## [2026-09-09] — Fase 4: Arquitectura Multi-Ciudad y Segunda Ciudad Real (Talca)

### 1. ¿Qué se implementó?
- **Correcciones Semánticas de Capas:**
  - Se eliminó la ambigüedad de rotular conexiones potenciales como `REAL`.
  - Badges estandarizados:
    * `OSM`: Ciclovías existentes mapeadas en OpenStreetMap.
    * `ALGORÍTMICO`: Rutas sugeridas calculadas algorítmicamente y conexiones potenciales detectadas sobre la red vial.
  - Actualización de descripciones en backend y frontend: *"Infraestructura y vías ciclistas mapeadas en OpenStreetMap"*, distinguiendo con absoluta claridad los datos físicos de los análisis predictivos.
- **Registro Central Declarativo (`registry.json`):**
  - Archivo maestro en `data/cities/registry.json` (y réplica estática en `frontend/public/data/cities/registry.json`).
  - Configuración completa para Curicó y Talca, más placeholders deshabilitados (`enabled: false`) para Rancagua, Chillán y Concepción.
- **Pipeline Unificado de Construcción (`pipeline/build_city.py`):**
  - CLI genérico parametrizado: `python -m pipeline.build_city --city {city_id} [--refresh] [--skip-gaps] [--all-enabled]`.
  - Resiliencia de red Overpass con rotación de 3 servidores (`overpass-api.de`, `kumi.systems`, `private.coffee`), timeouts de 90s/120s y reintentos exponenciales.
  - Orquestación automatizada de 6 pasos: ingesta OSM, construcción de grafo navegable, precomputación de rutas, detección de brechas Top 10, consolidación de métricas de red y sincronización estática hacia `frontend/public/`.
- **Segunda Ciudad Real: Talca (Región del Maule):**
  - **214 tramos de ciclovía mapeados** en OSM, totalizando **73.33 km** de infraestructura.
  - **Grafo navegable multimodal ($G_{\text{nav}}$)**: 31.529 nodos y 65.278 aristas (19.3 MB).
  - **30 componentes conexas**: Red dorsal principal de 28.60 km (39.0% del total) a lo largo del eje ferroviario y norte-sur.
  - **Top 10 brechas algorítmicas detectadas**:
    * #01 9 Norte (128 m, score 89.9): une la red dorsal (28.6 km) con la red nororiente (6.36 km), consolidando una red continua de 35.09 km (ganancia 272.2x).
    * #02 20 Norte A (599 m, score 82.5): une 35.09 km de red.
  - **5 rutas representativas urbanas calculadas y comparadas**: UTalca Campus Lircay a Plaza de Armas (4.86 km, 52.8% ciclovía), Mall Plaza Maule a Plaza de Armas, Río Claro a Plaza de Armas, La Florida a Plaza de Armas, Estación a UTalca.
- **Backend Multi-Ciudad (`backend/app/`):**
  - `CityRoutingManager`: Aislamiento estricto de instancias de routing por ciudad bajo demanda con bloqueo seguro de concurrencia.
  - Nuevos endpoints multi-ciudad y actualización de esquemas Pydantic (`CitySummary`, `CityDetail`).
  - Suite de tests unitarios completa (`backend/tests/test_multicity.py`): **31 de 31 tests pasando en 1.48s**.
- **Frontend Multi-Ciudad React + MapLibre:**
  - Selector de ciudad interactivo en encabezado (`CityHeader.tsx`).
  - Sincronización transparente de URLs (`?city=curico`, `?city=talca`) con soporte de navegación en historial (`popstate`).
  - Tarjeta de métricas urbanas `NetworkStatusCard.tsx` en la barra lateral derecha.
  - Presets dinámicos en el planificador de rutas según la ciudad activa.
  - Reinicio automático y seguro de estado entre transiciones de ciudad (cero geometrías fantasmas).
  - Scroll vertical fluido en `.right-sidebar` para acomodar capas, estado de red y lista de brechas en cualquier resolución.
  - Linter: **0 advertencias, 0 errores** (`oxlint`). Build de producción: **Exitoso** (`vite build`).
- **Control de Artefactos Pesados:**
  - `.gitignore` configurado para excluir descargas crudas volátiles (`raw_network.json`, `raw_cycleways.json`, `routes_cache.json`), manteniendo solo las capas GeoJSON y grafos de navegación requeridos para CI y tiempo de ejecución.

### 2. ¿Qué se comprobó visualmente en ejecución?
- Verificación automatizada exhaustiva mediante Chrome DevTools Protocol headless:
  - **`phase4_01_curico.png`:** Carga inicial en Curicó con badges `OSM` y `ALGORÍTMICO`, métricas (43.2 km, 121 tramos), selector de ciudad y tarjeta de estado.
  - **`phase4_02_talca.png`:** Transición interactiva a Talca: vuelo suave de cámara, 214 tramos en verde, Top 10 brechas en ámbar, 5 rutas sugeridas en azul, presets de Talca.
  - **`phase4_03_talca_gap_popup.png`:** Enfoque e inspección de la brecha #01 de Talca (9 Norte, 128 m) con popup de métricas de red y disclaimer.
  - **`phase4_04_talca_route.png`:** Cálculo interactivo en Talca (Plaza de Armas a Campus Lircay UTalca) mostrando 4.86 km, 52.8% en ciclovía, desglose de calles y comparación con ruta vehicular.
  - **`phase4_05_curico_back.png`:** Retorno dinámico a Curicó: reseteo limpio de rutas/brechas, cámara en Curicó, 121 tramos, cero capas residuales.
  - **`phase4_06_direct_talca.png`:** Acceso directo por URL en frío (`/?city=talca`): inicialización correcta en Talca.

---

## [2026-09-09] — Fase 3: Detector Algorítmico de Conexiones Faltantes para Curicó

### 1. ¿Qué se implementó?
- **Pipeline de Detección Algorítmica de Gaps (`pipeline/gap_detector.py`):**
  - Extracción estricta del subgrafo ciclista formal ($G_{\text{cycling}}$): ciclovías segregadas, ciclobandas y vías exclusivas, excluyendo calles comunes pedaleables.
  - Descomposición en componentes conexas: Se identificaron **31 componentes conexas** en Curicó (total: 42.22 km; componente mayor #1: 19.12 km, #2: 4.38 km).
  - Búsqueda determinista de brechas sobre la red vial transitable real ($G_{\text{nav}}$): Algoritmo de camino más corto que une componentes desconectadas a lo largo de calles existentes reales, descartando trazos rectos e inviabilidades topológicas.
  - Función de priorización multicriterio objetiva (`priority_score`, escala 0–100):
    * 35% Longitud de la brecha ($S_{\text{length}}$: menor distancia = mayor viabilidad inmediata).
    * 30% Magnitud de red unida ($S_{\text{network}}$: premia conectar con la componente principal).
    * 20% Eficiencia de ganancia ($S_{\text{gain}}$: ratio $\text{red\_unida} / \text{longitud\_brecha}$).
    * 15% Nivel de calma vial ($S_{\text{stress}}$: facilidad de implementación en calles de baja velocidad).
  - Deduplicación espacial de candidatos redundantes (>60% solapamiento).
  - Terminología prudente y rigurosa: *"Conexión potencial"*, *"Oportunidad detectada"*, *"Candidato algorítmico"*.
- **Reemplazo 100% Real de `missing-connections.geojson`:**
  - Se eliminaron por completo las geometrías conceptuales DEMO de Curicó.
  - Generación de los Top 10 candidatos algorítmicos reales (`is_demo: false`, `status: "ALGORITHMIC_CANDIDATE"`):
    1. **Manuel Antonio Caro (Score 75.9):** Brecha de 75 m por calle residencial tranquila que integra un ramal aislado de 420 m a la red principal de 19.12 km (ratio de ganancia 258.3x).
    2. **Enrique Lafourcade (Score 75.4):** Brecha de 834 m que une las dos mayores redes de Curicó (#1 de 19.12 km y #2 de 4.38 km), consolidando una red continua de 24.33 km.
    3. **Avenida Rauquén (Score 72.8):** 539 m uniendo 20.30 km de red.
    4. **Calle Membrillar (Score 72.0):** 460 m uniendo 20.14 km de red.
    5. **Avenida España (Score 71.0):** 517 m uniendo 20.00 km de red.
    6. **Avenida Circunvalación (Score 68.6):** 419 m uniendo 19.82 km de red.
    7. **Calle Carmen (Score 67.5):** 765 m uniendo 20.39 km de red.
    8. **Calle Prat (Score 65.5):** 609 m uniendo 19.80 km de red.
    9. **Calle Chacabuco (Score 64.9):** 593 m uniendo 19.78 km de red.
    10. **Avenida Camilo Henríquez (Score 64.6):** 456 m uniendo 19.64 km de red.
  - Sincronización en `data/cities/curico/missing-connections.geojson` y `frontend/public/data/cities/curico/missing-connections.geojson`.
- **Backend (`backend/app/` y `backend/tests/`):**
  - Actualización de metadatos de capa en `LAYER_DEFINITIONS["missing-connections"]`: nombre *"Conexiones potenciales"*, `is_demo: False`.
  - Suite de tests unitarios completa (`backend/tests/test_gap_detection.py`): Validación de fórmula de score, componentes sintéticas, propiedades de GeoJSON y consistencia de datos de Curicó.
  - Pytest: **26 tests pasando en 4.24s**.
- **Frontend Interactivo (React + MapLibre):**
  - Componente `OpportunitiesList.tsx`: Panel interactivo que lista el Top 10 de oportunidades ordenado por prioridad, mostrando badge de puntaje, distancia de brecha, red unida, ganancia y descripción vial. Permite enfocar la cámara (`fitBounds`) y activar el resalto de la brecha.
  - Resalto y Selección en `MapView.tsx`: Capa de resalto visual ámbar (`casing-selected-gap` y `line-selected-gap`) y popups enriquecidos con badge `OPORTUNIDAD ALGORÍTMICA`, desglose de métricas y disclaimer de prudencia técnica.
  - Contenedor elástico `.right-sidebar`: Agrupa `LayerControl` y `OpportunitiesList` en un flujo vertical sin solapamientos en ninguna resolución de pantalla, con botón de colapso/expansión.
  - Corrección de condición de carrera en inicialización de estado de capas en `App.tsx`.
  - Linter: **0 errores, 0 advertencias** (`oxlint`).
  - Build: **Exitoso** (`vite build`).

### 2. ¿Qué se comprobó visualmente en ejecución?
- Se ejecutó verificación visual automatizada vía Chrome CDP headless (`scratch/verify_phase3_gaps.js`):
  - **Captura 1 (`phase3_01_gaps_map.png`):** Mapa general con 121 ciclovías (verde) y 10 conexiones potenciales algorítmicas (ámbar discontinuo) junto al panel lateral de oportunidades.
  - **Captura 2 (`phase3_02_gap_selected_popup.png`):** Selección del candidato #01 (Manuel Antonio Caro, 75 m), halo de resalto ámbar y popup con métricas completas (Score 75.9/100, Red unida: 19.54 km, Ratio: 258.3x).
  - **Captura 3 (`phase3_03_gap2_selected_popup.png`):** Selección del candidato #02 (Enrique Lafourcade, 834 m), uniendo los dos ejes ciclistas más grandes de Curicó en una red de 24.33 km.
  - **Captura 4 (`phase3_04_minimized_panel.png`):** Panel de oportunidades minimizado sin colisionar con el control de capas.

---

## [2026-09-09] — Fase 2: Motor de Routing Ciclista Determinista para Curicó

### 1. ¿Qué se implementó?
- **Motor de Routing Determinista en Python (`pipeline/`):**
  - Función de costo ciclista calibrada (`pipeline/cost_function.py`):
    * $\text{costo} = \text{distancia} \times \text{penalización}$.
    * Ciclovías segregadas protegidas (0.70), ciclovías dedicadas (0.78), ciclobandas (0.88), calles calmas 30 km/h (0.95), calles residenciales (1.05), arterias secundarias (1.90), arterias primarias rápidas (2.60).
    * Autopistas vehiculares y vías con `access=no` / `bicycle=no` bloqueadas ($\infty$).
    * Reglas de sentido único y excepciones ciclistas (`oneway:bicycle=no`, contraflujo).
  - Extractor y constructor de grafo (`pipeline/network_extractor.py`, `pipeline/graph_builder.py`):
    * Descarga y caché local de la red vial completa de Curicó (`raw_network.json`).
    * Conversión a `networkx.DiGraph` dirigido (16,252 nodos y 33,545 aristas en componente conexa principal).
    * Serialización optimizada a `data/cities/curico/nav_graph.json`.
  - Enrutador A* con Heurística Admisible (`pipeline/router.py`):
    * Ajuste espacial (`SpatialNodeIndex`) con umbral estricto de 500 metros.
    * Búsqueda de camino con A* usando $h(u, v) = \text{haversine}(u, v) \times 0.70$ (estrictamente admisible y monotónica).
    * Cálculo simultáneo de la ruta ciclista y la ruta físicamente más corta para comparación de métricas (+% distancia vs +% ciclovía ganada).
- **Reemplazo 100% Real de Rutas Sugeridas:**
  - Se eliminaron las geometrías conceptuales DEMO de `suggested-routes.geojson`.
  - Se calcularon 5 rutas representativas reales en Curicó siguiendo la red vial de OSM:
    1. **Ruta Norte (Rauquén $\rightarrow$ Plaza de Armas):** 4.39 km | **52.9% ciclovías** vs 4.20 km (20% ciclovías) en ruta corta (+32.9% de ciclovía segura con solo +190 m de desvío).
    2. **Ruta Oriente (Zapallar $\rightarrow$ Plaza de Armas):** 4.23 km | **70.8% ciclovías** vs 2.97 km (14.7% ciclovías).
    3. **Ruta Poniente (Santa Fe $\rightarrow$ Plaza de Armas):** 2.58 km | **16.2% ciclovías** vs 2.42 km (0% ciclovías).
    4. **Circuito Universitario (Los Niches $\rightarrow$ Plaza de Armas):** 2.39 km | **46.7% ciclovías** vs 2.30 km (0% ciclovías).
    5. **Eje Intermodal (Guaiquillo $\rightarrow$ Estación de Trenes):** 4.08 km | **42.3% ciclovías** vs 3.63 km (4.7% ciclovías).
- **Backend API REST (`backend/app/`):**
  - Endpoint `POST /api/cities/{city_id}/route` con validación Pydantic (`RouteRequest`, `RouteResponse`).
  - Motor de routing `CityRoutingEngine` cargado en memoria para respuestas $< 10\text{ ms}$.
  - Sistema de caché bidireccional en memoria y disco (`routes_cache.json`).
  - 22 tests unitarios pasando en 0.81s (`pytest`).
- **Interfaz Interactiva de Usuario (React + MapLibre):**
  - Componente `RoutePlanner.tsx`:
    * Selección interactiva de Origen y Destino mediante clics sobre el mapa o presets urbanos.
    * Pines A (verde) y B (rojo) en el mapa.
    * Trazado de ruta activa en azul eléctrico (`#2563eb`) con casing realzado.
    * Opción para mostrar trazado vehicular alternativo más corto en naranja discontinuo.
    * Panel con comparador de métricas: distancia, % de ciclovía, ganancia ciclista y calles recorridas.
  - Actualización de Popups:
    * Badge `RUTA RECOMENDADA ALGORÍTMICA` (reemplaza DEMO).
    * Desglose completo de métricas de infraestructura y trayecto.

### 2. ¿Qué se comprobó visualmente en ejecución?
- Se ejecutó verificación visual automatizada vía Chrome CDP headless (`scratch/verify_phase2_routing.js`):
  - **Captura 1 (`phase2_01_initial_map.png`):** Mapa inicial cargando los 121 tramos de ciclovías y las 5 rutas algorítmicas siguiendo las calles reales de Curicó.
  - **Captura 2 (`phase2_02_route_calculated.png`):** Ruta activa calculada entre Rauquén y Plaza de Armas (4.39 km, 52.9% ciclovía) con pines A y B sobre el mapa.
  - **Captura 3 (`phase2_03_route_comparison.png`):** Comparación visual y panel de métricas desplegado.
  - **Captura 4 (`phase2_04_route_popup.png`):** Popup interactivo sobre ruta recomendada mostrando badge azul `RUTA RECOMENDADA ALGORÍTMICA`, trayecto y desglose de ganancia ciclista (+32.9%).

---

## [2026-09-09] — Iteración 1.2: Diagnóstico Causa Raíz de Renderizado y Resolución de API / API Key

### 1. ¿Qué se diagnosticó y resolvió en ejecución?
- **Diagnóstico Causa Raíz 1 (Bloqueo en Web Worker de MapLibre en Vite):**
  - Al ejecutar la aplicación con Chrome headless e inspeccionar vía Chrome DevTools Protocol (CDP), se descubrió que las fuentes GeoJSON tenían `loaded: false`, `_isUpdatingWorker: true` y `_pendingWorkerUpdate: true` de forma permanente.
  - Causa real: MapLibre GL JS v6 intenta cargar su Web Worker desde `./maplibre-gl-worker.mjs` relativo a `import.meta.url`, lo que en Vite resolvía a `http://localhost:5173/node_modules/.vite/deps/maplibre-gl-worker.mjs` arrojando un error **HTTP 404 (Not Found)**. Sin el worker activo, MapLibre no podía procesar ni teselar los datos GeoJSON para la GPU.
  - Solución: Se importó el worker explícitamente vía Vite URL query (`import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'`) y se registró globalmente con `setWorkerUrl(maplibreWorkerUrl)`. Vite ahora sirve el worker con HTTP 200 en desarrollo y lo empaqueta en `dist/assets/` en producción.
- **Diagnóstico Causa Raíz 2 (Bloqueo por `isStyleLoaded()` en `MapView.tsx`):**
  - `syncMapLayers` contenía la guarda `if (!map || !map.isStyleLoaded()) return;`.
  - En MapLibre GL JS, `map.isStyleLoaded()` verifica si *todas* las fuentes y teselas raster del estilo han completado su carga (`this.style.loaded()`). Dado que las teselas del mapa base se descargan asíncronamente en segundo plano, `isStyleLoaded()` retornaba `false` tanto al momento de disparar `load` como cuando el estado de `layersData` terminaba de llegar.
  - Solución: Se reemplazó la guarda por un ref de inicialización `isLayersInitializedRef`. En cuanto las fuentes y capas existen en el mapa, `source.setData(data)` y `map.setLayoutProperty()` se ejecutan inmediatamente sin depender del estado de carga de las teselas raster.
- **Diagnóstico Causa Raíz 3 (Destrucción y recreación del mapa por referencia de array):**
  - El hook `useEffect` de inicialización del mapa dependía de `[city.center, city.initial_zoom]`. Debido a que `city.center` es un array (`[-71.2394, -34.9854]`), cada actualización del estado `setCity(curico)` generaba una nueva referencia de array en JavaScript, destruyendo (`map.remove()`) y recreando el mapa innecesariamente.
  - Solución: Se cambió la dependencia a `[city.id]`, asegurando que el mapa se monte una sola vez y solo se recree si cambia la ciudad seleccionada.
- **Diagnóstico y Resolución del Aviso "API / API Key":**
  - Causa real descubierta visualmente en la inspección: Las teselas raster de CARTO Voyager (`basemaps.cartocdn.com`) comenzaron a requerir autenticación obligatoria en su servicio gratuito, imprimiendo una marca de agua diagonal repetida en cada tesela con el texto **"API KEY REQUIRED carto.com/basemapsapikey"**.
  - Solución: Se migró el mapa base a las teselas oficiales de **OpenStreetMap** (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`). Son 100% de código abierto, comunitarias, de alta fidelidad, no requieren claves de API ni tokens, y eliminan por completo cualquier marca de agua invasiva.

### 2. ¿Qué se comprobó visualmente en ejecución (Pruebas Reales)?
- Se ejecutó un script CDP interactivo con Chrome (`scratch/verify_rendering.js`) sobre la aplicación en vivo (`http://localhost:5173`):
  - **82 tramos de ciclovías existentes (REAL)** renderizados en **verde esmeralda** sobre el centro y periferia de Curicó.
  - **5 tramos de conexiones faltantes (DEMO)** renderizados en **ámbar discontinuo**.
  - **4 corredores de rutas sugeridas (DEMO)** renderizados en **azul**.
  - **Popups interactivos**: Al simular clic en el tramo "Lago Calafquén", se despliega exitosamente el popup seguro con badge `DATOS OPENSTREETMAP`, tipología `Infraestructura ciclista sobre calle (segregada / track)`, superficie `paved` y extensión `0.17 km (169.3 m)`.
  - **Control Maestro**: Al apagar la "Capa CicloConecta", todas las líneas ciclistas desaparecen instantáneamente (`visibility: none`) y la UI entra en modo inactivo. Al reactivarla, las líneas reaparecen sin recargar el mapa.
  - **Cero errores de consola** y **cero marcas de agua** de claves de API.

### 3. Evidencias y Pruebas
- Captura de pantalla verificada: `scratch/map_rendered_verified.png`
- Captura de pantalla de popup activo: `scratch/map_with_popup.png`
- Captura de pantalla con toggle apagado: `scratch/toggle_master_off.png`
- Tests automatizados: **13/13 pasados** (`pytest`).
- Linter frontend: **0 errores, 0 advertencias** (`oxlint`).
- Compilación de producción: **Exitosa** (`vite build`).

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
