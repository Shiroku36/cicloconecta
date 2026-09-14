# Planificador Algorítmico de Expansión de Red Ciclista (Fases 3.5 y 3.6)

Este documento describe los principios, la formulación matemática, el algoritmo de descubrimiento inductivo mediante clustering espacial, el **crecimiento topológico iterativo mediante red activa** y los resultados del **Planificador Algorítmico de Expansión de Red Ciclista** implementado para Curicó y Talca en CicloConecta.

---

## 1. Distinción Estructural: Conexiones Faltantes vs. Expansión de Red

En CicloConecta existen dos capas analíticas complementarias con propósitos de planificación urbana radicalmente distintos:

| Criterio | Conexiones Potenciales (`missing-connections`) | Expansión Territorial de Red (`network-expansion`) |
| :--- | :--- | :--- |
| **Pregunta que responde** | *¿Dónde una pequeña conexión une ciclovías ya existentes?* | *¿Hacia dónde conviene extender la red para llegar a barrios desatendidos?* |
| **Topología** | Relleno de brechas cortas (gaps $\le 1.200\text{ m}$) entre dos componentes ciclistas existentes. | Corredores estructurantes continuos ($0.5\text{ km} \le L \le 3.5\text{ km}$) que crecen topológicamente desde la red activa hacia el tejido urbano periférico. |
| **Extremo final** | Debe terminar obligatoriamente en otra ciclovía existente. | Termina en un polo habitacional, educativo o de equipamiento sin ciclovía actual. |
| **Insignia cartográfica** | `ALGORÍTMICO` (Amarillo/Ámbar `#b45309`) | `ANÁLISIS` (Violeta/Morado `#8b5cf6`) |
| **Naturaleza física** | Propuesta analítica de completitud de red. | Propuesta de planificación territorial progresiva por fases jerarquizadas. |

> [!IMPORTANT]
> Ninguna de las dos capas representa infraestructura existente con financiamiento garantizado. Por ello, ambas se etiquetan con insignias de análisis prudente (`ALGORÍTMICO` / `ANÁLISIS`) y disclaimers explícitos.

---

## 2. Metodología Inductiva y Ética de Datos (Sin Anclas Manuales)

### Prohibición de Inventar Población y Feat de Anclas
El modelo **no contiene anclas manuales codificadas ni coordenadas hardcodeadas** (`get_city_anchors` y `get_debug_manual_anchors` completamente eliminados del código de producción). Tampoco utiliza estimaciones de "habitantes beneficiados" no auditables.

En su lugar, el pipeline opera de manera 100% inductiva desde OpenStreetMap:
1. **Nodos de Acceso Urbano ($V_{\text{access}}$):** Nodos viales de calles `residential`, `living_street`, `service`, `unclassified`, `pedestrian`, `footway` y `track` dentro del límite urbano funcional. Cada nodo representa un punto físico de acceso a la trama habitacional y actividades urbanas.
2. **Deduplicación Espacial de POIs ($P_{\text{poi}}$):**
   - Agrupación por proximidad absoluta: POIs a $< 15\text{ m}$ de distancia independientemente de su nombre se fusionan en un único equipamiento representativo.
   - Agrupación nominal: POIs dentro de la misma categoría a $< 150\text{ m}$ con nombres normalizados coincidentes (ej. canchas múltiples de un mismo complejo deportivo o edificios de un mismo campus) se consolidan.
   - *Curicó:* 592 POIs brutos $\to$ 551 POIs únicos desduplicados.
   - *Talca:* 982 POIs brutos $\to$ 905 POIs únicos desduplicados.
3. **Bandas de Distancia a la Red Ciclista:**
   - Para cada nodo de acceso urbano se evalúa la distancia geodésica a la infraestructura ciclista más cercana:
     * $0 - 250\text{ m}$ (inmediata)
     * $250 - 500\text{ m}$ (caminable / pedaleable corta)
     * $500 - 1.000\text{ m}$ (distancia media)
     * $> 1.000\text{ m}$ (desatención crítica)
   - Umbral de cobertura local: $R_{\text{cov}} = 400\text{ m}$. Todo nodo a $> 400\text{ m}$ se clasifica como *desatendido*.
4. **Clustering Territorial Espacial (DBSCAN Determinista):**
   - Se ejecuta DBSCAN espacial sobre los nodos desatendidos con $\varepsilon = 300\text{ m}$ y $\text{min\_samples} = 20$.
   - Esto agrupa de forma puramente algorítmica las concentraciones densas de viviendas y equipamientos periféricos sin sesgo humano.
   - *Curicó:* 28 clusters territoriales descubiertos.
   - *Talca:* 21 clusters territoriales descubiertos.
5. **Selección Automatizada de Anclas por Cluster:**
   - En cada cluster, se selecciona como ancla principal el nodo que maximiza la densidad barrial (nodos a $\le 250\text{ m}$), la cercanía a POIs esenciales (a $\le 350\text{ m}$) y la centralidad geométrica al centroide del cluster.
   - Para clusters extensos ($> 250$ nodos), se genera adicionalmente un ancla secundaria a $\ge 550\text{ m}$ del ancla principal.
   - La denominación del sector se extrae de la calle más frecuente en el cluster combinada con el hito o POI más próximo (ej. "Sector Mataquito", "Sector 14 Sur").

---

## 3. Crecimiento Topológico Real: Red Activa Dinámica (Fase 3.6)

### El Problema del Modelo Estático ("Efecto Estrella")
En el modelo inicial (Fase 3.5), todos los corredores candidatos se generaban una sola vez desde la red ciclista base de OSM. Como consecuencia:
- Las fases posteriores (Fase 2, 3, etc.) solo podían nacer de la red existente original.
- El sistema tendía a abrir ramas independientes radiales hacia la periferia ("efecto estrella"), seleccionando a veces caminos rurales largos y desarticulados (ej. Ruta J-624 en Curicó) en lugar de continuar ejes densos recién proyectados.
- Las fases no podían encadenarse topológicamente.

### Arquitectura de `ActiveCyclingNetwork`
Para solucionar esto, en la Fase 3.6 se implementó la clase `ActiveCyclingNetwork`:

```text
Iteración 0: Red Activa = Ciclovías Base OSM
Para cada fase k in [1..6]:
  1. Recalcular nodos desatendidos (> 400m de Red Activa)
  2. Identificar clusters activos prioritarios
  3. Regenerar corredores candidatos trazando Dijkstra inverso hacia la Red Activa
  4. Evaluar candidatos con scoring dinámico no constante
  5. Seleccionar mejor corredor C_k
  6. Identificar dependencias: si C_k contacta a C_j (j < k), agregar a depends_on
  7. Clasificar tipología: trunk_extension, continuation, branch, cross_connector
  8. Añadir geometría de C_k a Red Activa (nodos, aristas, fuentes y spatial grid)
  9. Actualizar conjunto de nodos y POIs cubiertos
```

### Clasificación Topológica de Corredores (`expansion_type`)
Cada propuesta recibe una tipología determinista y una lista explícita de dependencias (`depends_on`):

| Tipología | Definición | Regla Algorítmica |
| :--- | :--- | :--- |
| `trunk_extension` | Extensión de eje estructurante | Continuación a lo largo de la misma vía arterial o extensión directa de un eje jerárquico. |
| `continuation` | Continuación de fase previa | Se empalma directamente en el extremo o cuerpo de una fase anterior del plan maestro. |
| `branch` | Ramificación territorial | Nace de la red existente y penetra en un nuevo sector habitacional desatendido. |
| `cross_connector` | Conector transversal de red | Vincula transversalmente dos corredores o cierra bucles de circulación urbana. |

---

## 4. Función de Puntuación Multicriterio Dinámica ($S_{\text{expansion}} \in [0, 100]$)

$$S_{\text{expansion}}(C) = S_{\text{cov}} + S_{\text{poi}} + S_{\text{cont}} + S_{\text{axis}} + S_{\text{eff}}$$

1. **Ganancia de Cobertura Residencial ($S_{\text{cov}} \le 35\text{ pts}$):**
   $$S_{\text{cov}} = \min\left(35, \frac{\Delta N_{\text{access}}}{300} \cdot 35\right)$$
   Mide la cantidad de nodos de acceso urbano que pasan de $> 400\text{ m}$ a $\le 400\text{ m}$ de la **red activa**.
2. **Incorporación de Equipamientos POI ($S_{\text{poi}} \le 25\text{ pts}$):**
   $$S_{\text{poi}} = \min\left(25, \frac{\Delta P_{\text{poi}}}{8} \cdot 25\right)$$
   Mide los colegios, centros de salud, comercios y servicios antes desatendidos que quedan integrados a la red activa.
3. **Continuidad Dinámica con la Red Activa ($S_{\text{cont}} \in [8.0, 20.0\text{ pts}]$):**
   En lugar del puntaje fijo anterior de $20.0$, $S_{\text{cont}}$ evalúa la calidad del contacto topológico:
   - **Base:** $10.0\text{ pts}$ por contacto físico formal con la red activa.
   - **Bonificación por Extensión Troncal (`trunk_extension`):** $+4.0\text{ pts}$ si prolonga el mismo eje vial estructurante.
   - **Bonificación por Cierre de Bucle (`cross_connector`):** $+3.0\text{ pts}$ si conecta simultáneamente con dos sectores activos.
   - **Bonificación por Red Troncal Base:** $+3.0\text{ pts}$ si conecta directamente con la componente ciclista principal (> 5 km).
   - **Penalización Periférica / Rural:** $-3.0\text{ pts}$ si el trazado discurre predominantemente por caminos no urbanizados (`track`, `unclassified` sin POIs).
4. **Puntaje de Eje Estructurante (`structural_axis_score`, $5.0 - 10.0\text{ pts}$):**
   Premia trazados que discurren por vías de mayor jerarquía conectiva (`secondary`, `tertiary`) aptas como avenidas colectoras.
5. **Eficiencia Territorial ($S_{\text{eff}} \le 10\text{ pts}$):**
   $$S_{\text{eff}} = \min\left(10, \frac{\Delta N_{\text{access}} / L_{\text{km}}}{180} \cdot 10\right)$$
   Premia corredores con alta densidad de beneficio por kilómetro de red proyectada.

---

## 5. Clasificación de Contexto Urbano vs. Periurbano

Para distinguir de forma prudente y transparente el entorno de cada propuesta sin inventar datos sociodemográficos, se clasifica cada fase en:
- **`urban` ("Expansión Urbana"):** Trazado en trama residencial consolidada (`residential`, `secondary`, `tertiary`), alta densidad de POIs ($\ge 2$ en 400 m) y baja presencia de pistas rurales ($< 25\%$).
- **`periurban` ("Conector Periurbano"):** Trazado con más del 30% en vías `track` o `unclassified`, sinónimo de camino rural, o con densidad nula de POIs y baja densidad de accesos habitacionales.
- **`uncertain` ("Mixto / Transición"):** Zonas de borde urbano en proceso de desarrollo.

---

## 6. Validación Empírica y Benchmark A/B en Curicó

Para verificar el impacto del crecimiento topológico real frente al modelo estático anterior, se ejecutó una comparativa A/B directa con datos reales de Curicó:

| Métrica de Evaluación | Modelo Estático (Fase 3.5) | Crecimiento Topológico (Fase 3.6) | Variación |
| :--- | :--- | :--- | :--- |
| **Longitud total proyectada** | 7.84 km | **6.83 km** | **-1.01 km (-13% menos asfalto)** |
| **Nodos de acceso ganados** | 1.142 nodos | 1.097 nodos | -3.9% (equivalente) |
| **POIs incorporados a la red** | 50 POIs | **55 POIs** | **+5 POIs (+10% más servicios)** |
| **Eficiencia de cobertura** | 145.7 nodos/km | **160.6 nodos/km** | **+10.2% mayor eficiencia** |
| **Topología de red** | 6 ramas aisladas ("estrella") | **Ejes continuos con dependencias** | Estructuración orgánica |
| **Comportamiento en Fase 6** | Ruta J-624 (2.61 km rural, 3 POIs) | **Continuación Callejón San José (1.52 km, 5 POIs, Escuela Olga Figueroa)** | Alta utilidad barrial |

### Fases Resultantes en Curicó (Fase 3.6)
1. **Fase 1 (Score 95.0, `branch`, Urbano):** Sector Mataquito (0.90 km, +217 nodos, +21 POIs).
2. **Fase 2 (Score 94.0, `branch`, Urbano):** Sector Callejón San José / Rauquén Norte (1.53 km, +226 nodos, +12 POIs).
3. **Fase 3 (Score 80.8, `branch`, Urbano):** Sector Nazareth / Salcobrand (0.92 km, +129 nodos, +8 POIs).
4. **Fase 4 (Score 75.4, `branch`, Urbano):** Sector Nueva América / Colegio Cristiano (0.73 km, +153 nodos, +5 POIs).
5. **Fase 5 (Score 72.8, `branch`, Periurbano):** Sector Ruta J-630 (1.23 km, +222 nodos, +4 POIs).
6. **Fase 6 (Score 69.8, `continuation`, Urbano):** Sector Callejón San José Norte (1.52 km, +150 nodos, +5 POIs). **Depende de Fase 2 (`expansion-curico-02`)**, alcanzando la Escuela María Olga Figueroa Leyton y consolidando un eje continuo de 3.05 km.

### Fases Resultantes en Talca (Fase 3.6)
1. **Fase 1 (Score 99.6, `branch`, Urbano):** Sector 14 Sur (0.83 km, +247 nodos, +21 POIs).
2. **Fase 2 (Score 98.8, `branch`, Urbano):** Sector 26 Sur / La Florida (1.86 km, +508 nodos, +20 POIs).
3. **Fase 3 (Score 97.4, `branch`, Urbano):** Sector Calle 27 Oriente (0.78 km, +234 nodos, +12 POIs).
4. **Fase 4 (Score 96.0, `trunk_extension`, Urbano):** Sector Calle 34 Oriente (0.98 km, +557 nodos, +7 POIs). **Depende de Fase 3 (`expansion-talca-03`)**, extendiendo el eje hacia el norte.
5. **Fase 5 (Score 95.0, `branch`, Urbano):** Sector Calle 31 Oriente (0.83 km, +318 nodos, +11 POIs).
6. **Fase 6 (Score 86.6, `branch`, Urbano):** Sector 26 Sur Oriente (0.53 km, +227 nodos, +5 POIs).