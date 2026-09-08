# CicloConecta 🚲🇨🇱

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![City: Curicó](https://img.shields.io/badge/Piloto-Curicó%2C%20Chile-0284c7.svg)](#primera-ciudad-curicó)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](backend/)
[![Frontend: React+MapLibre](https://img.shields.io/badge/Frontend-React%20%7C%20MapLibre-blue.svg)](frontend/)

**CicloConecta** es una plataforma comunitaria y de código abierto para **visualizar, analizar y proyectar la movilidad ciclista en ciudades de Chile**.

No busca competir con aplicaciones comerciales de navegación satelital vehicular (como Google Maps o Waze), sino proporcionar una **capa especializada de inteligencia ciclista** montada sobre mapas libres y abiertos, permitiendo a la ciudadanía, activistas y planificadores urbanos entender dónde se pedalea de forma segura y dónde la red está fracturada.

---

## 🗺️ Primera Ciudad: Curicó, Chile

La primera fase del proyecto se enfoca en la ciudad de **Curicó, Región del Maule**, caracterizada por una topografía predominantemente plana con gran potencial para la bicicleta, pero con desafíos de continuidad e interconexión entre sectores residenciales y el centro cívico.

### Capas Disponibles en esta Versión

1. **Ciclovías Existentes (DATOS REALES):**
   - Más de 120 tramos de vías ciclistas activas extraídos directamente desde **OpenStreetMap (OSM)** mediante la API Overpass (Avenida Bernardo O'Higgins, Rauquén, Calafquén, Merced, Tutuquén, Paso Nivel Los Niches, etc.), sumando más de **43 kilómetros** de infraestructura mapeada.
2. **Conexiones Faltantes (DEMO / ESTIMACIÓN CONCEPTUAL):**
   - Tramos y cortes críticos identificados preliminarmente para unir sectores desconectados (ej. enlace Rauquén con la Estación Curicó).
3. **Rutas Sugeridas (DEMO / ESTIMACIÓN CONCEPTUAL):**
   - Corredores alternativos de bajo estrés vehicular por calles residenciales (zona 30 km/h) para sortear vías saturadas.

> [!NOTE]
> Para garantizar total transparencia comunitaria, las capas no verificadas en terreno están marcadas con un badge explícito **`DEMO`** en la interfaz y en los atributos del GeoJSON. Nunca presentamos estimaciones preliminares como infraestructura real.

---

## 🏛️ Principio de Arquitectura: Desacoplamiento

El sistema separa estrictamente dos mundos:

- **Preprocesamiento Determinista (Offline/Batch en Python):** El análisis topológico vial, cálculo de distancias y detección de discontinuidades de red se procesan una sola vez mediante algoritmos de grafos deterministas, generando capas GeoJSON estandarizadas. **No se utiliza IA para cálculos geométricos o de conectividad**.
- **Visualizador Liviano (Cliente en React + MapLibre GL JS):** El navegador únicamente descarga las capas GeoJSON procesadas y las renderiza aceleradas por GPU sobre un mapa base libre (Carto / OpenStreetMap), garantizando una experiencia fluida (60 FPS) tanto en escritorio como en dispositivos móviles.

---

## 📂 Estructura del Repositorio

```text
cicloconecta/
├── data/
│   └── cities/
│       └── curico/
│           ├── city.json                        # Metadatos espaciales, centroide y estadísticas
│           ├── cycling-infrastructure.geojson   # Datos REALES extraídos de OpenStreetMap
│           ├── missing-connections.geojson      # Datos DEMO claramente identificados
│           └── suggested-routes.geojson         # Datos DEMO claramente identificados
├── pipeline/
│   ├── osm_extractor.py                         # Extractor determinista desde OSM Overpass
│   └── requirements.txt
├── backend/
│   ├── app/
│   │   ├── main.py                              # FastAPI REST API (/api/cities, /api/layers)
│   │   ├── config.py                            # Configuración de entornos y CORS
│   │   └── schemas.py                           # Validación de esquemas con Pydantic
│   ├── tests/
│   │   └── test_api.py                          # Tests automatizados de endpoints
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── MapView.tsx                      # Renderizador WebGL con MapLibre GL JS
│   │   │   ├── LayerControl.tsx                 # Panel flotante reactivo de capas
│   │   │   ├── CityHeader.tsx                   # Cabecera con estadísticas e identidad
│   │   │   └── InfoModal.tsx                    # Modal de transparencia y metodología
│   │   ├── services/api.ts                      # Consumo de API con fallback estático
│   │   └── styles/index.css                     # Diseño moderno con glassmorphism
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   ├── ARCHITECTURE.md                          # Arquitectura detallada del sistema
│   ├── ROADMAP.md                               # Fases de expansión a otras ciudades de Chile
│   ├── DATA_PIPELINE.md                         # Especificación del pipeline determinista
│   └── DECISIONS.md                             # Registro de decisiones de arquitectura (ADRs)
└── LICENSE                                      # Licencia MIT
```

---

## 🚀 Inicio Rápido en Local

### Requisitos Previos
- **Node.js** 18+ y npm
- **Python** 3.10+

---

### Opción 1: Ejecutar Frontend (Con datos locales o API)

El frontend está diseñado con fallback estático inteligente: funciona inmediatamente por sí solo consumiendo los GeoJSON locales, o conectándose al backend si está activo.

```bash
# 1. Entrar a la carpeta frontend
cd frontend

# 2. Instalar dependencias
npm install

# 3. Iniciar servidor de desarrollo Vite
npm run dev
```

Abre en tu navegador: **`http://localhost:5173`**.

---

### Opción 2: Ejecutar Backend API (FastAPI)

```bash
# 1. Instalar dependencias de Python
pip install -r backend/requirements.txt

# 2. Iniciar el servidor FastAPI con Uvicorn
uvicorn backend.app.main:app --reload --port 8000
```

- API disponible en: **`http://localhost:8000`**
- Documentación interactiva Swagger en: **`http://localhost:8000/docs`**

---

### Ejecutar Tests Automatizados

```bash
# Tests del backend
pytest backend/tests/

# Verificación de compilación y linter frontend
npm --prefix frontend run lint
npm --prefix frontend run build
```

---

### Re-ejecutar el Pipeline de Datos de Curicó

Para volver a consultar OpenStreetMap y actualizar el GeoJSON de infraestructura ciclista existente:

```bash
python pipeline/osm_extractor.py
```

---

## 📈 Próximos Pasos (Hoja de Ruta)

- [ ] **Fase 2:** Implementar el algoritmo determinista de detección automática de *gaps* viales con NetworkX / Shapely.
- [ ] **Fase 3:** Escalar a nuevas ciudades de la Región del Maule (Talca, Linares) y otras regiones de Chile (Concepción, Valparaíso, Santiago).
- [ ] **Fase 4:** Mecanismos de retroalimentación ciudadana para reportar baches, falta de señalización u obstáculos en ciclovías.

Para mayor detalle técnico, consulta [`docs/ROADMAP.md`](docs/ROADMAP.md) y [`docs/DECISIONS.md`](docs/DECISIONS.md).

---

## 🤝 Licencia y Comunidad

Proyecto distribuido bajo la licencia libre **MIT**. Consulta el archivo [`LICENSE`](LICENSE) para más detalles.
Las contribuciones comunitarias son bienvenidas.
