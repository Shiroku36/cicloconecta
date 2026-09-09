# CicloConecta 🚲🇨🇱

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Ciudades: Curicó & Talca](https://img.shields.io/badge/Ciudades-Curicó%20%7C%20Talca-0284c7.svg)](#ciudades-activas)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](backend/)
[![Frontend: React+MapLibre](https://img.shields.io/badge/Frontend-React%20%7C%20MapLibre-blue.svg)](frontend/)

**CicloConecta** es una plataforma comunitaria y de código abierto para **visualizar, analizar y proyectar la movilidad ciclista en ciudades de Chile**.

No busca competir con navegadores vehiculares comerciales, sino proporcionar una **capa especializada de inteligencia ciclista territorial** montada sobre mapas abiertos, permitiendo a la ciudadanía, activistas y planificadores urbanos entender dónde se pedalea de forma segura, dónde la red está fracturada y cómo priorizar intervenciones de alto impacto.

---

## 🗺️ Ciudades Activas

CicloConecta opera con una **arquitectura multi-ciudad genérica y declarativa** gobernada por [`data/cities/registry.json`](data/cities/registry.json). El sistema incluye actualmente:

| Ciudad | Región | Ciclovías Mapeadas | Tramos OSM | Componentes Conexas | Brechas Top 10 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Curicó** | Región del Maule | 43.20 km | 121 tramos | 31 componentes | #01: Manuel Antonio Caro (75 m) |
| **Talca** | Región del Maule | 73.33 km | 214 tramos | 30 componentes | #01: 9 Norte (128 m, une 35 km) |

> [!NOTE]
> Nuevas comunas (Rancagua, Chillán, Gran Concepción) están registradas como placeholders y listas para construirse con un único comando CLI. Ver [`docs/MULTI_CITY.md`](docs/MULTI_CITY.md).

---

## 🚲 Capas y Metodología Rigurosa

Para garantizar total transparencia comunitaria, distinguimos estrictamente la infraestructura física existente de los análisis predictivos:

1. **Ciclovías Existentes (Badge `OSM`):**
   - Vías ciclistas activas extraídas directamente de **OpenStreetMap** (segregadas, ciclobandas y vías exclusivas).
2. **Conexiones Potenciales (Badge `ALGORÍTMICO`):**
   - Brechas prioritarias de continuidad calculadas algorítmicamente mediante descomposición de componentes conexas y caminos mínimos sobre la red vial real ($G_{\text{nav}}$).
3. **Rutas Sugeridas (Badge `ALGORÍTMICO`):**
   - Rutas calculadas con algoritmo A* determinista minimizando el estrés vehicular y priorizando ciclovías con respecto a la ruta vehicular directa.

---

## 🏛️ Principio de Arquitectura: Desacoplamiento

El sistema separa estrictamente el cómputo geoespacial del consumo web:

- **Pipeline Determinista Unificado (`pipeline/build_city.py`):** Descarga datos de OpenStreetMap con redundancia de servidores Overpass, construye el grafo navegable en NetworkX, analiza componentes conexas, computa brechas y precalcula rutas representativas. **No se utiliza IA generativa para cálculos geométricos o de conectividad**.
- **Motor de Routing FastAPI (`backend/`):** Aislamiento estricto de instancias de routing por ciudad en memoria para responder consultas interactivas en $< 15\text{ ms}$.
- **Visualizador React + MapLibre GL JS (`frontend/`):** Interfaz fluida acelerada por hardware (60 FPS), selector de ciudades con sincronización de URLs (`?city=talca`), tarjeta de estado de red (`NetworkStatusCard`), planificador con presets urbanos y popups detallados con resalto de brechas.

---

## 📂 Estructura del Repositorio

```text
cicloconecta/
├── data/
│   └── cities/
│       ├── registry.json                        # Registro central declarativo de ciudades
│       ├── curico/                              # Artefactos procesados de Curicó
│       │   ├── city.json                        # Metadatos, centroide, métricas y conectividad
│       │   ├── cycling-infrastructure.geojson   # Ciclovías existentes (OSM)
│       │   ├── missing-connections.geojson      # Brechas prioritarias algorítmicas (Top 10)
│       │   ├── suggested-routes.geojson         # Rutas sugeridas representativas
│       │   └── nav_graph.json                   # Grafo vial navegable (16.252 nodos)
│       └── talca/                               # Artefactos procesados de Talca
│           ├── city.json                        # Metadatos, centroide, métricas y conectividad
│           ├── cycling-infrastructure.geojson   # Ciclovías existentes (214 tramos, 73.3 km)
│           ├── missing-connections.geojson      # Brechas prioritarias algorítmicas (Top 10)
│           ├── suggested-routes.geojson         # Rutas sugeridas representativas
│           └── nav_graph.json                   # Grafo vial navegable (31.529 nodos)
├── pipeline/
│   ├── build_city.py                            # CLI unificado para construir cualquier ciudad
│   ├── osm_extractor.py                         # Extractor de ciclovías desde Overpass
│   ├── network_extractor.py                     # Extractor de red vial navegable
│   ├── gap_detector.py                          # Detector multicriterio de brechas de red
│   └── router.py                                # Motor de routing determinista A*
├── backend/
│   ├── app/
│   │   ├── main.py                              # FastAPI REST API (/api/cities, /api/cities/{id}/route)
│   │   ├── routing/                             # RoutingEngine y CityRoutingManager
│   │   └── schemas.py                           # Validación de esquemas Pydantic
│   └── tests/                                   # 31 tests unitarios automatizados (pytest)
├── frontend/
│   ├── src/
│   │   ├── components/                          # MapView, CityHeader, RoutePlanner, OpportunitiesList, NetworkStatusCard
│   │   ├── services/api.ts                      # Consumo de API REST y fallback estático
│   │   └── styles/index.css                     # Estilos modernos con glassmorphism
│   └── public/data/cities/                      # Réplica estática para despliegue sin backend
├── docs/
│   ├── MULTI_CITY.md                            # Guía paso a paso para sumar nuevas ciudades
│   ├── ARCHITECTURE.md                          # Arquitectura detallada del sistema
│   ├── DATA_PIPELINE.md                         # Especificación matemática del pipeline
│   ├── DECISIONS.md                             # Registro de decisiones de arquitectura (ADRs)
│   └── PROGRESS.md                              # Bitácora histórica de avances por fase
└── LICENSE                                      # Licencia MIT
```

---

## 🚀 Inicio Rápido en Local

### Requisitos Previos
- **Node.js** 18+ y npm
- **Python** 3.10+

---

### Opción 1: Ejecutar Frontend (Con fallback estático o API)

```bash
# 1. Instalar dependencias
npm --prefix frontend install

# 2. Iniciar servidor Vite
npm --prefix frontend run dev
```

Abre en tu navegador: **`http://localhost:5173`** (o directamente **`http://localhost:5173/?city=talca`**).

---

### Opción 2: Ejecutar Backend API (FastAPI)

```bash
# 1. Instalar dependencias
pip install -r backend/requirements.txt

# 2. Iniciar servidor FastAPI
uvicorn backend.app.main:app --reload --port 8000
```

- API: **`http://localhost:8000`**
- Swagger UI: **`http://localhost:8000/docs`**

---

### Ejecutar Tests Automatizados

```bash
# Backend (31 tests unitarios)
pytest backend/tests/

# Frontend (linter y compilación estricta de tipos)
npm --prefix frontend run lint
npm --prefix frontend run build
```

---

### Construir o Actualizar una Ciudad

```bash
# Construir Talca completa desde OpenStreetMap
python -m pipeline.build_city --city talca

# Re-procesar todas las ciudades activas
python -m pipeline.build_city --all-enabled
```

---

## 🤝 Licencia y Comunidad

Proyecto distribuido bajo la licencia libre **MIT**. Consulta el archivo [`LICENSE`](LICENSE) para más detalles.
Las contribuciones comunitarias y aportes a OpenStreetMap son bienvenidos.

