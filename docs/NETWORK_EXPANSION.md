# Planificador Algorítmico de Expansión de Red Ciclista (Fase 3.5)

Este documento describe los principios, la formulación matemática, el algoritmo de crecimiento voraz y los resultados del **Planificador Algorítmico de Expansión de Red Ciclista** implementado para Curicó en CicloConecta.

---

## 1. Distinción Estructural: Conexiones Faltantes vs. Expansión de Red

En CicloConecta existen dos capas analíticas complementarias con propósitos de planificación urbana radicalmente distintos:

| Criterio | Conexiones Potenciales (`missing-connections`) | Expansión Territorial de Red (`network-expansion`) |
| :--- | :--- | :--- |
| **Pregunta que responde** | *¿Dónde una pequeña conexión une ciclovías ya existentes?* | *¿Hacia dónde conviene extender la red para llegar a barrios desatendidos?* |
| **Topología** | Relleno de brechas cortas (gaps $\le 1.200\text{ m}$) entre dos componentes ciclistas existentes. | Corredores estructurantes continuos ($0.5\text{ km} \le L \le 3.5\text{ km}$) desde la red ciclista hacia el tejido urbano periférico. |
| **Extremo final** | Debe terminar obligatoriamente en otra ciclovía existente. | Termina en un polo habitacional, educativo o de equipamiento sin ciclovía actual. |
| **Insignia cartográfica** | `ALGORÍTMICO` (Amarillo/Ámbar `#b45309`) | `ANÁLISIS` (Violeta/Morado `#8b5cf6`) |
| **Naturaleza física** | Propuesta analítica de completitud. | Propuesta de planificación territorial progresiva por fases. |

> [!IMPORTANT]
> Ninguna de las dos capas representa infraestructura existente con financiamiento garantizado. Por ello, ambas se etiquetan con insignias de análisis prudente (`ALGORÍTMICO` / `ANÁLISIS`) y disclaimers explícitos.

---

## 2. Proxy de Cobertura Urbana y Ética de Datos

### Prohibición de Inventar Población
El modelo **no utiliza estimaciones de "habitantes beneficiados"** ni censos proyectados no verificables a nivel de manzana. 

En su lugar, se utiliza un modelo riguroso y transparente fundamentado exclusivamente en OpenStreetMap:
1. **Grafo de Nodos Residenciales ($V_{\text{res}}$):** Nodos viales de calles `residential`, `living_street`, `service` y `unclassified` dentro del límite urbano funcional. Cada nodo representa un punto físico de acceso a hogares y actividades cotidianas.
2. **Puntos de Interés Verificados ($P_{\text{poi}}$):** Equipamientos esenciales mapeados en OSM con etiquetas `amenity`, `shop`, `leisure`, `tourism` y `healthcare` (colegios, centros de salud CESFAM/SAPU, farmacias, supermercados, plazas, clubes deportivos, terminales de transporte).
3. **Radio de Cobertura Caminable / Ciclista Local ($R_{\text{cov}} = 400\text{ m}$):** Estándar de accesibilidad urbana equivalente a 5 minutos caminando o 1.5 minutos en bicicleta a velocidad de paseo.

### Cobertura Base Inicial de Curicó
Al evaluar los 16.252 nodos viales y 592 POIs de Curicó frente a los 43.2 km de ciclovías existentes:
- **Nodos residenciales cubiertos a $\le 400\text{ m}$:** 69.5%
  - $0 - 250\text{ m}$: 8.900 nodos
  - $250 - 500\text{ m}$: 3.301 nodos
  - $500 - 1.000\text{ m}$: 1.757 nodos
  - $> 1.000\text{ m}$: 2.294 nodos
- **POIs cubiertos a $\le 400\text{ m}$:** 78.7% (466 de 592 equipamientos)

Los sectores fuera del radio de 400 m corresponden a macro-zonas habitacionales consolidadas: **Rauquén Norte / Don Sebastián**, **Santa Fe / Alessandri Poniente**, **Sarmiento / Villa El Sol**, **Mataquito / Licantén**, **Zapallar Oriente** y **Tutuquén**.

---

## 3. Algoritmo de Trazado de Corredores (Reverse Dijkstra Óptimo)

Para evitar la "dispersión en árbol" de un Dijkstra directo hacia múltiples destinos, el algoritmo utiliza un enfoque determinista de **Reverse Dijkstra**:
1. Para cada polo o macro-sector desatendido, se identifica su nodo representativo más denso en equipamiento y trama habitacional ($v_{\text{target}}$).
2. Se ejecuta un Dijkstra inverso desde $v_{\text{target}}$ sobre la red vial ciclable hasta alcanzar una ciclovía existente en la red base ($v_{\text{cycleway}}$).
3. **Función de Costo Vial de Expansión:**
   $$w(u, v) = \text{dist}(u, v) \cdot \mu_{\text{highway}} \cdot \mu_{\text{penalties}}$$
   - Vías estructurantes colectoras (`secondary`, `tertiary`) tienen factor $\mu = 1.0$ (permiten trazados directos aptos para ciclovías segregadas).
   - Calles residenciales tranquilas (`residential`, `living_street`) tienen factor $\mu = 1.05 - 1.15$.
   - Vías troncales no segregables (`trunk`, `primary`) tienen penalización severa ($\mu = 2.5 - 3.5$) para evitar enviar ciclistas por autopistas.
4. **Filtro de Calidad Geométrica:**
   - Longitud mínima: $500\text{ m}$; máxima: $3.500\text{ m}$.
   - Trazado sinuoso controlado: Razón de sinuosidad $\frac{L_{\text{red}}}{D_{\text{euclid}}} \le 1.30$. En Curicó, los corredores seleccionados tienen razones entre $1.09$ y $1.20$.

---

## 4. Función Objetivo de Puntuación Multicriterio ($S_{\text{expansion}} \in [0, 100]$)

Cada corredor candidato $C$ es evaluado de acuerdo con la función:

$$S_{\text{expansion}}(C) = S_{\text{cov}} + S_{\text{poi}} + S_{\text{cont}} + S_{\text{qual}} + S_{\text{eff}}$$

Donde:
1. **Ganancia de Cobertura Residencial ($S_{\text{cov}} \le 35\text{ pts}$):**
   $$S_{\text{cov}} = \min\left(35, \frac{\Delta N_{\text{res}}}{300} \cdot 35\right)$$
   Mide la cantidad de nodos residenciales que pasan de estar a $>400\text{ m}$ de la red ciclista a quedar cubiertos dentro del radio de influencia del nuevo corredor.
2. **Incorporación de Destinos y POIs Clave ($S_{\text{poi}} \le 25\text{ pts}$):**
   $$S_{\text{poi}} = \min\left(25, \frac{\Delta P_{\text{poi}}}{8} \cdot 25\right)$$
   Mide los colegios, centros de salud y equipamientos antes desatendidos que se suman a la red.
3. **Continuidad con la Red Base ($S_{\text{cont}} = 20\text{ pts}$):**
   Garantiza que el corredor nazca directamente como ramal de la red ciclista existente o de una fase previa ya incorporada.
4. **Jerarquía y Aptitud Vial ($S_{\text{qual}} \in [7.5, 10]\text{ pts}$):**
   Premia trazados que discurren por avenidas con perfil vial suficiente para alojar infraestructura ciclista segregada de alto estándar.
5. **Eficiencia Territorial ($S_{\text{eff}} \le 10\text{ pts}$):**
   $$S_{\text{eff}} = \min\left(10, \frac{\text{Ratio}}{180} \cdot 10\right), \quad \text{donde } \text{Ratio} = \frac{\Delta N_{\text{res}}}{L_{\text{km}}}$$
   Favorece corredores con alta densidad de ganancia por kilómetro construido.

---

## 5. Crecimiento Voraz por Fases (Greedy Iterative Expansion)

El plan no propone un conjunto inconexo de obras simultáneas. Emplea un proceso iterativo voraz en el que cada fase expande la red y actualiza el estado de cobertura territorial:

1. Evaluar todos los corredores candidatos contra la red base inicial.
2. Seleccionar el candidato con mayor puntaje $S_{\text{expansion}} \to \text{Fase 1}$.
3. **Actualizar el buffer territorial:** Los nodos y POIs cubiertos por la Fase 1 pasan a considerarse "cubiertos".
4. Re-evaluar los candidatos restantes: sus ganancias $\Delta N_{\text{res}}$ y $\Delta P_{\text{poi}}$ se calculan considerando únicamente el territorio que **todavía sigue sin cobertura**. Esto previene sobre-estimar beneficios de corredores superpuestos.
5. Seleccionar la siguiente mejor opción $\to \text{Fase } k$, hasta completar el plan maestro.

---

## 6. Plan Maestro de Expansión Territorial de Curicó (6 Fases)

| Fase | Nombre del Corredor | Sector Beneficiado | Longitud | Cobertura Ganada | POIs Nuevos | Score | Ejes Principales |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **1** | **Eje Norte: Av. Rauquén Norte → Don Sebastián** | Rauquén Norte / Don Sebastián | 1.21 km | +229 nodos (+1.41%) | +12 POIs | **91.7** | Av. Rauquén, Av. Arturo Prat, Mateo de Toro |
| **2** | **Eje Surponiente: Mataquito → Villa Mejillones** | Mataquito / Licantén | 0.89 km | +206 nodos (+1.27%) | +23 POIs | **89.0** | Balmaceda, Mataquito, Azapa, Camina |
| **3** | **Eje Oriente: Av. Zapallar Oriente** | Zapallar Oriente | 0.89 km | +122 nodos (+0.75%) | +6 POIs | **80.8** | Av. Zapallar, Pasaje 10 |
| **4** | **Eje Poniente: Santa Fe → Trapiche Poniente** | Santa Fe Poniente | 0.77 km | +117 nodos (+0.72%) | +11 POIs | **79.6** | Río Huasco, Los Sauces, Trapiche Poniente |
| **5** | **Eje Norponiente: Tutuquén Poniente** | Tutuquén / Bombero Garrido | 0.89 km | +87 nodos (+0.54%) | +4 POIs | **74.1** | Tutuquén, Pasaje Los Aromos |
| **6** | **Eje Norte Exterior: Conexión Sarmiento** | Sarmiento / Villa El Sol | 0.94 km | +52 nodos (+0.32%) | +0 POIs | **70.0** | Caletera Ruta 5, Los Cristales |
| **Total** | **Plan Maestro Curicó** | **6 Macro-Sectores** | **5.59 km** | **+813 nodos (+5.0%)** | **+56 POIs** | — | — |

---

## 7. Integración en CicloConecta

- **Pipeline (`pipeline/expansion_planner.py`):** Módulo autónomo integrado en el paso `[5/7]` de `pipeline/build_city.py`. Tiempos de ejecución: 1.6 segundos para Curicó.
- **Backend API (`backend/app/main.py`):** Capa registrada en `LAYER_DEFINITIONS` con color `#8b5cf6`, badge `ANÁLISIS` y esquema Pydantic extendido en `CitySummary`.
- **Frontend Interactivo (`ExpansionPlanCard.tsx`, `MapView.tsx`):**
  - Componente colapsable `ExpansionPlanCard` con métricas globales (+5.6 km, +813 nodos, +56 POIs).
  - Trazado de líneas moradas con halo de selección (`casing-selected-expansion` / `line-selected-expansion`).
  - Popups con formato seguro en el DOM (sin interpolación HTML insegura), mostrando fase, score, longitud, ganancia de nodos, POIs incorporados y advertencia prudente.
