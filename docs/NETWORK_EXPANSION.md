# Planificador Algorítmico de Expansión de Red Ciclista (Fase 3.5)

Este documento describe los principios, la formulación matemática, el algoritmo de descubrimiento inductivo mediante clustering espacial y los resultados del **Planificador Algorítmico de Expansión de Red Ciclista** implementado para Curicó y Talca en CicloConecta.

---

## 1. Distinción Estructural: Conexiones Faltantes vs. Expansión de Red

En CicloConecta existen dos capas analíticas complementarias con propósitos de planificación urbana radicalmente distintos:

| Criterio | Conexiones Potenciales (`missing-connections`) | Expansión Territorial de Red (`network-expansion`) |
| :--- | :--- | :--- |
| **Pregunta que responde** | *¿Dónde una pequeña conexión une ciclovías ya existentes?* | *¿Hacia dónde conviene extender la red para llegar a barrios desatendidos?* |
| **Topología** | Relleno de brechas cortas (gaps $\le 1.200\text{ m}$) entre dos componentes ciclistas existentes. | Corredores estructurantes continuos ($0.5\text{ km} \le L \le 3.5\text{ km}$) desde la red ciclista hacia el tejido urbano periférico. |
| **Extremo final** | Debe terminar obligatoriamente en otra ciclovía existente. | Termina en un polo habitacional, educativo o de equipamiento sin ciclovía actual. |
| **Insignia cartográfica** | `ALGORÍTMICO` (Amarillo/Ámbar `#b45309`) | `ANÁLISIS` (Violeta/Morado `#8b5cf6`) |
| **Naturaleza física** | Propuesta analítica de completitud de red. | Propuesta de planificación territorial progresiva por fases. |

> [!IMPORTANT]
> Ninguna de las dos capas representa infraestructura existente con financiamiento garantizado. Por ello, ambas se etiquetan con insignias de análisis prudente (`ALGORÍTMICO` / `ANÁLISIS`) y disclaimers explícitos.

---

## 2. Metodología Inductiva y Ética de Datos (Sin Anclas Manuales)

### Prohibición de Inventar Población y Feat de Anclas
El modelo **no contiene anclas manuales codificadas ni coordenadas hardcodeadas** (`get_city_anchors` o condicionales de ciudad eliminados en producción). Tampoco utiliza estimaciones de "habitantes beneficiados" no auditables.

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

## 3. Generación Multi-Alternativa de Corredores

Para cada ancla identificada se generan múltiples trazados alternativos hacia la red ciclista:
1. **Alternativa Directa (Mínimo Esfuerzo / Menor Estrés):**
   Dijkstra inverso que prioriza vías secundarias, terciarias y residenciales tranquilas, minimizando longitud y desvíos.
2. **Alternativa de Eje Estructurante (Avenida Colectora / Conectividad Arterial):**
   Dijkstra con bonificación para vías estructurantes (`secondary`, `tertiary`) para propender a corredores continuos con mayor visibilidad urbana.
3. **Control de Calidad Geométrica:**
   - Longitud requerida: $500\text{ m} \le L \le 3.500\text{ m}$.
   - Límite de sinuosidad: $\frac{L_{\text{red}}}{D_{\text{euclidea}}} \le 1.35$.
   - Superposición máxima con ciclovías ya existentes: $< 30\%$.
   - Geometría real: Cada tramo se apoya estrictamente sobre el grafo navegable real, sin líneas rectas aéreas.

---

## 4. Función de Puntuación Multicriterio ($S_{\text{expansion}} \in [0, 100]$)

$$S_{\text{expansion}}(C) = S_{\text{cov}} + S_{\text{poi}} + S_{\text{cont}} + S_{\text{axis}} + S_{\text{eff}}$$

1. **Ganancia de Cobertura Residencial ($S_{\text{cov}} \le 35\text{ pts}$):**
   $$S_{\text{cov}} = \min\left(35, \frac{\Delta N_{\text{access}}}{300} \cdot 35\right)$$
   Mide la cantidad de nodos de acceso urbano que pasan de $> 400\text{ m}$ a $\le 400\text{ m}$ gracias al nuevo corredor.
2. **Incorporación de Equipamientos POI ($S_{\text{poi}} \le 25\text{ pts}$):**
   $$S_{\text{poi}} = \min\left(25, \frac{\Delta P_{\text{poi}}}{8} \cdot 25\right)$$
   Mide los colegios, centros de salud, comercios y servicios antes desatendidos que quedan integrados a la red.
3. **Continuidad con la Red Base ($S_{\text{cont}} = 20\text{ pts}$):**
   Garantiza que el corredor conecte físicamente con la red ciclista formal o con una fase previa del plan maestro.
4. **Puntaje de Eje Estructurante (`structural_axis_score`, $5.0 - 10.0\text{ pts}$):**
   Premia trazados que discurren por ejes de mayor jerarquía conectiva (`secondary`, `tertiary`) aptos como avenidas colectoras. **No se realizan afirmaciones de ancho o perfil físico vial** a menos que conste explícitamente en los tags de OSM.
5. **Eficiencia Territorial ($S_{\text{eff}} \le 10\text{ pts}$):**
   $$S_{\text{eff}} = \min\left(10, \frac{\Delta N_{\text{access}} / L_{\text{km}}}{180} \cdot 10\right)$$
   Premia corredores con alta densidad de beneficio por kilómetro de red proyectada.

---

## 5. Crecimiento Voraz Iterativo por Fases (Greedy Master Plan)

El plan maestro se construye iterativamente:
1. En cada iteración se evalúan todos los corredores candidatos contra el estado actual de cobertura.
2. Se selecciona el candidato con mayor puntaje $S_{\text{expansion}}$.
3. Los nodos de acceso y POIs beneficiados se incorporan al conjunto de cubiertos.
4. La geometría del corredor se suma a la red ciclista proyectada, permitiendo que fases posteriores puedan ramificarse desde él.
5. Se recalculan las ganancias marginales $\Delta N$ y $\Delta P$ para evitar duplicación de beneficios.

---

## 6. Resultados Comparados: Curicó y Talca

### Curicó (Descubrimiento Inductivo)
- **Infraestructura Base:** 43.2 km (121 tramos OSM). Cobertura base: 67.7% nodos de acceso ($\le 400\text{ m}$), 78.4% POIs.
- **Detección Territorial:** 28 clusters desatendidos descubiertos algorítmicamente.
- **Plan Maestro Generado (6 Fases, +7.84 km, +1.181 nodos ganados, +50 POIs incorporados):**
  1. **Fase 1 (Score 95.0):** Sector Mataquito (0.90 km, +217 nodos, +21 POIs).
  2. **Fase 2 (Score 94.0):** Sector Callejón San José / Rauquén Norte (1.53 km, +226 nodos, +12 POIs).
  3. **Fase 3 (Score 80.8):** Sector Nazareth / Salcobrand (0.92 km, +129 nodos, +8 POIs).
  4. **Fase 4 (Score 75.4):** Sector Nueva América / Colegio Cristiano (0.73 km, +153 nodos, +5 POIs).
  5. **Fase 5 (Score 73.4):** Sector Ruta J-630 (1.15 km, +226 nodos, +1 POI).
  6. **Fase 6 (Score 68.5):** Sector Ruta J-624 / Convento Viejo (2.61 km, +202 nodos, +3 POIs).

*Comparación con el modelo anterior de anclas manuales:*
El descubrimiento inductivo identificó los mismos macro-sectores habitacionales críticos (Mataquito, Rauquén Norte, Nueva América, Santa Fe) pero de manera 100% auditable, eliminando el sesgo del operador y capturando con mayor precisión los ejes de mayor densidad habitacional real.

### Talca (Generalización Exitosa)
- **Infraestructura Base:** 73.33 km (214 tramos OSM). Cobertura base: 74.5% nodos de acceso ($\le 400\text{ m}$), 81.3% POIs.
- **Detección Territorial:** 21 clusters desatendidos descubiertos algorítmicamente.
- **Plan Maestro Generado (6 Fases, +5.72 km, +2.126 nodos ganados, +78 POIs incorporados):**
  1. **Fase 1 (Score 99.6):** Sector 14 Sur (0.83 km, +247 nodos, +21 POIs).
  2. **Fase 2 (Score 98.8):** Sector 26 Sur / La Florida (1.86 km, +508 nodos, +20 POIs).
  3. **Fase 3 (Score 97.4):** Sector Calle 27 Oriente (0.78 km, +234 nodos, +12 POIs).
  4. **Fase 4 (Score 95.9):** Sector Calle 34 Oriente (0.89 km, +548 nodos, +7 POIs).
  5. **Fase 5 (Score 95.0):** Sector Calle 31 Oriente (0.83 km, +318 nodos, +11 POIs).
  6. **Fase 6 (Score 86.6):** Sector 26 Sur Oriente (0.53 km, +227 nodos, +5 POIs).