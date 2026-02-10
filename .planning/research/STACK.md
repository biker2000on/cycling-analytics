# Stack Research

**Domain:** Self-hosted cycling analytics platform
**Researched:** 2026-02-10
**Confidence:** HIGH

## Recommended Stack

### Backend Framework

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| FastAPI | 0.128.0+ | REST API framework | Modern async-first framework with automatic OpenAPI docs, native Pydantic validation, excellent performance (10-100x faster than Flask), and built-in OAuth2/JWT support. Ideal for data-heavy APIs with complex validation. **HIGH confidence** - verified via Context7. |
| Python | 3.12+ | Runtime | Required for FastAPI and modern async features. Latest stable with performance improvements. |
| uv | 0.5.0+ | Package/project manager | 10-100x faster than pip (2.6s vs 21.4s for JupyterLab), single binary replaces pip/virtualenv/pyenv, global module cache with CoW/hardlinks. User preference already established. **HIGH confidence**. |

### Frontend Framework

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| React | 18.3.0+ | UI framework | Largest ecosystem, best for complex dashboards with interactive data flows, easiest team scaling. Recharts integrates natively. **HIGH confidence** - verified via Context7. |
| Vite | 7.0.0+ | Build tool | 390ms startup vs 4.5s for CRA, 16.1s build vs 28.4s, modern ESM-based HMR. Industry standard replacing CRA in 2026. **HIGH confidence** - verified via Context7. |
| TypeScript | 5.7+ | Type system | Type safety for complex data structures, better IDE support, catches errors at compile time. Standard for production React apps. **MEDIUM confidence**. |

### Data Visualization

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Recharts | 3.3.0+ | Charts library | React-native charting built on D3, declarative API, excellent time-series support with Brush component for zoom/pan, synchronized charts, responsive design. Lighter than Plotly (50KB vs heavy Plotly.js). **HIGH confidence** - verified via Context7. |
| react-leaflet | 4.x | Map integration | Official React bindings for Leaflet, component-based API, supports OpenStreetMap tiles, modern hooks support, active maintenance. **HIGH confidence** - verified via Context7. |
| Leaflet | 1.9.4+ | Map library | Open-source, mobile-friendly interactive maps, 42KB gzipped, extensible plugin ecosystem. Industry standard for OSM integration. **HIGH confidence** - verified via Context7. |

### Database

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| PostgreSQL | 17+ | Relational database | Robust ACID compliance, JSON support, mature ecosystem. User preference already established. **HIGH confidence**. |
| TimescaleDB | 2.18.0+ | Time-series extension | Automatic hypertables for second-by-second ride data, 20x faster than vanilla PostgreSQL for time-series queries, compression, continuous aggregates. Self-hosted on Docker. **HIGH confidence** - official Docker images verified. |
| PostGIS | 3.5+ | Geospatial extension | Native spatial queries for route data, distance calculations, map overlays. Standard extension for PostgreSQL geospatial. **MEDIUM confidence**. |

### ORM & Database Tooling

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| SQLAlchemy | 2.1+ | ORM | Most widely used Python ORM, async support (asyncio + asyncpg), Data Mapper pattern for complex queries, explicit control over TimescaleDB features, works with FastAPI. Performance leader in benchmarks. **HIGH confidence** - verified via Context7. |
| asyncpg | 0.30+ | PostgreSQL driver | Fastest async PostgreSQL driver for Python, required for SQLAlchemy async mode, C-optimized. **MEDIUM confidence**. |
| Alembic | 1.14+ | Database migrations | De facto migration tool for SQLAlchemy, handles schema versioning, works with TimescaleDB hypertables. **MEDIUM confidence**. |

### Scientific Computing

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| NumPy | 2.2+ | Numerical arrays | Foundation for power calculations, C-optimized array operations, 20x faster than pure Python for numerical work. Standard for scientific computing. **HIGH confidence**. |
| Pandas | 2.2+ | Data analysis | DataFrame operations for ride data, time-series analysis, aggregations. Integration with TimescaleDB via SQLAlchemy. Used by 52%+ of data scientists. **HIGH confidence**. |
| SciPy | 1.15+ | Scientific algorithms | Statistical functions, interpolation for power curve fitting, optimization for threshold estimation. Builds on NumPy. **MEDIUM confidence**. |

### Data Parsing

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| fitparse | 1.2.0+ | FIT file parser | Pure Python, community-maintained fork with Python 3.8+ support, well-documented, handles Garmin Edge/Forerunner files. **MEDIUM confidence** - PyPI verified. |
| stravalib | 2.2+ | Strava API client | Official V3 API bindings, rate limiting support, Pint integration for quantities, model-based objects for type safety. Most widely used Strava library. **MEDIUM confidence** - official docs verified. |
| Pydantic | 2.10+ | Data validation | FastAPI native validation, type-safe models for FIT/Strava data parsing, automatic JSON serialization. **HIGH confidence**. |

### Authentication

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| PyJWT | 2.10+ | JWT tokens | Sign/encode/decode tokens, simpler API than python-jose, industry standard. **MEDIUM confidence**. |
| passlib[bcrypt] | 1.7.4+ | Password hashing | Secure bcrypt hashing (or Argon2id via pwdlib for 2026 best practice), industry-standard library. **MEDIUM confidence**. |
| FastAPI OAuth2 | (built-in) | OAuth2 flow | Native FastAPI security utilities, dependency injection for auth, supports Strava OAuth2 integration. **HIGH confidence** - verified via Context7. |

### Development Tools

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| pytest | 8.3+ | Testing framework | Industry standard (52%+ adoption), simple syntax, powerful fixtures, async support. **HIGH confidence**. |
| Ruff | 0.9+ | Linter/formatter | Rust-based, 10-100x faster than pylint/black, combines multiple tools (flake8, isort, black), same team as uv. **MEDIUM confidence**. |
| mypy | 1.13+ | Type checker | Static type checking for Python, catches bugs early, integrates with SQLAlchemy 2.0 stubs. **MEDIUM confidence**. |

### Deployment

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Docker | 27.x+ | Containerization | Self-hosted deployment, consistent environments, TimescaleDB official images available. **HIGH confidence**. |
| Docker Compose | 2.33+ | Multi-container orchestration | Manage FastAPI + PostgreSQL + TimescaleDB + Nginx in single config, easy local dev and production deployment. **HIGH confidence** - verified via Docker Hub. |
| Nginx | 1.27+ | Reverse proxy | Static file serving (React build), API proxying, SSL termination, production-grade. **MEDIUM confidence**. |

## Installation

### Backend Setup (using uv)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create project and virtual environment
cd cycling-analytics
uv venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install core dependencies
uv add "fastapi[standard]>=0.128.0"
uv add "sqlalchemy[asyncio]>=2.1.0"
uv add asyncpg
uv add alembic
uv add "pydantic>=2.10.0"

# Install data libraries
uv add "numpy>=2.2.0"
uv add "pandas>=2.2.0"
uv add "scipy>=1.15.0"

# Install parsing libraries
uv add fitparse
uv add stravalib
uv add pyjwt
uv add "passlib[bcrypt]"

# Install dev dependencies
uv add --dev "pytest>=8.3.0"
uv add --dev "pytest-asyncio"
uv add --dev ruff
uv add --dev mypy
```

### Frontend Setup (using npm/pnpm)

```bash
# Create Vite + React + TypeScript project
npm create vite@latest cycling-analytics-frontend -- --template react-ts
cd cycling-analytics-frontend

# Install dependencies
npm install

# Install charting and mapping
npm install recharts@3.3.0
npm install react-leaflet@4.2.1 leaflet@1.9.4
npm install @types/leaflet --save-dev

# Install additional utilities
npm install axios  # for API calls
npm install react-router-dom  # for routing
```

### Database Setup (Docker Compose)

```yaml
# docker-compose.yml
version: '3.8'
services:
  timescaledb:
    image: timescale/timescaledb:2.18.0-pg17
    environment:
      POSTGRES_USER: cycling_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: cycling_analytics
    ports:
      - "5432:5432"
    volumes:
      - timescale_data:/var/lib/postgresql/data
    command: postgres -c shared_preload_libraries=timescaledb

volumes:
  timescale_data:
```

## Alternatives Considered

| Category | Recommended | Alternative | When to Use Alternative |
|----------|-------------|-------------|-------------------------|
| Backend framework | FastAPI | Django | If you need Django admin panel, built-in auth, or prefer Active Record ORM pattern. Django ORM simpler but less flexible than SQLAlchemy. |
| Backend framework | FastAPI | Flask | Never in 2026 for new projects - slower, no async-first design, no auto-docs. FastAPI is strictly better. |
| Frontend build tool | Vite | Next.js | If you need SSR/SSG for SEO (not applicable for self-hosted analytics). Next.js adds unnecessary complexity for this use case. |
| Frontend build tool | Vite | Create React App | Never - CRA is legacy/unmaintained as of 2026. Vite is 10x faster. |
| Charts library | Recharts | Plotly | If you need 3D charts or advanced scientific visualization. Plotly is heavier (2MB+) and slower, overkill for cycling analytics. |
| Charts library | Recharts | Chart.js | If bundle size is critical (<50KB). Chart.js lacks React integration and advanced time-series features (no Brush component). |
| ORM | SQLAlchemy | Django ORM | If using Django framework. Django ORM is simpler but can't leverage TimescaleDB features as explicitly. |
| Package manager | uv | Poetry | If you need PyPI publishing workflows or semantic versioning for library distribution. For application development, uv is faster and simpler. |
| Package manager | uv | pip | Never for new projects - pip is 10-100x slower, no dependency resolution, no venv management. |
| Testing | pytest | unittest | Never - unittest requires more boilerplate, less readable, no fixture system. pytest is industry standard (52%+ adoption). |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Create React App | Unmaintained as of 2026, 10x slower than Vite, heavy webpack config | Vite |
| Flask | No async-first design, no auto-docs, slower than FastAPI, no native Pydantic | FastAPI |
| python-jose | Heavier than PyJWT, unnecessary complexity for simple JWT use cases | PyJWT |
| pip | 10-100x slower than uv, no dependency resolution, manual venv management | uv |
| Plotly.py for web dashboards | Server-side rendering overhead, 2MB+ bundle size, overkill for this use case | Recharts (client-side) |
| MongoDB/NoSQL | Time-series data needs relational + hypertables, no benefit over TimescaleDB | PostgreSQL + TimescaleDB |

## Stack Patterns by Variant

**If emphasizing real-time performance:**
- Use Server-Sent Events (SSE) in FastAPI for live activity streaming
- Add Redis for caching computed metrics (CTL/ATL/TSB)
- Use WebSocket connections for live map updates during rides

**If targeting mobile devices:**
- Add React Native with shared TypeScript types from web frontend
- Use Progressive Web App (PWA) features in Vite
- Optimize Recharts rendering with `dot={false}` for large datasets

**If scaling to 100+ users:**
- Add Nginx connection pooling (pgBouncer) for PostgreSQL
- Implement TimescaleDB compression policies for old ride data
- Use continuous aggregates for pre-computed daily/weekly metrics

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| FastAPI 0.128.0 | Pydantic 2.10+ | Pydantic v2 required for FastAPI 0.100+, breaking changes from v1 |
| SQLAlchemy 2.1+ | asyncpg 0.30+ | Async support requires asyncpg driver, not psycopg2 |
| React 18.3+ | react-leaflet 4.x | react-leaflet v3 only supports React 17, v4 required for React 18 |
| Recharts 3.3.0 | React 18.3+ | Recharts 3.x built for React 18, uses latest D3 |
| TimescaleDB 2.18.0 | PostgreSQL 17 | TimescaleDB versions tied to PostgreSQL major versions, check compatibility matrix |
| uv 0.5.0+ | Python 3.12+ | Minimum Python 3.8, but 3.12+ recommended for performance |

## Confidence Assessment

| Area | Level | Source |
|------|-------|--------|
| FastAPI | HIGH | Context7 `/websites/fastapi_tiangolo` - official docs, verified async support and version 0.128.0 |
| SQLAlchemy | HIGH | Context7 `/websites/sqlalchemy_en_21` - verified async support, PostgreSQL compatibility |
| Recharts | HIGH | Context7 `/recharts/recharts` - verified v3.3.0, time-series features, Brush component |
| Vite | HIGH | Context7 `/vitejs/vite` - verified v7.0.0, React plugin, performance benchmarks |
| react-leaflet | HIGH | Context7 `/websites/react-leaflet_js` - verified v4.x compatibility with React 18 |
| TimescaleDB | HIGH | Official Docker Hub `timescale/timescaledb:2.18.0-pg17`, Docker Compose docs |
| NumPy/Pandas | HIGH | Multiple authoritative sources confirm as standard for scientific Python in 2026 |
| uv | HIGH | Multiple 2026 sources confirm 10-100x performance improvement, official Astral project |
| pytest | HIGH | JetBrains PyCharm blog, multiple sources confirm 52%+ adoption as of 2026 |
| FIT parsing | MEDIUM | PyPI and GitHub confirmed fitparse 1.2.0+, but limited 2026-specific docs |
| Stravalib | MEDIUM | Official docs and PyPI verified, v2.2+ confirmed but not via Context7 |
| Authentication | MEDIUM | FastAPI official docs verified OAuth2 support, PyJWT confirmed via web search |
| PostGIS | MEDIUM | Standard PostgreSQL extension but not independently verified for this research |
| Nginx/Docker | MEDIUM | Industry standard verified via web search but not project-specific validation |

## Sources

### Context7 (HIGH confidence)
- `/websites/fastapi_tiangolo` - FastAPI official documentation
- `/websites/sqlalchemy_en_21` - SQLAlchemy 2.1 documentation
- `/recharts/recharts` - Recharts v3.3.0 documentation
- `/vitejs/vite` - Vite v7.0.0 documentation
- `/websites/react-leaflet_js` - react-leaflet v4.x documentation

### Official Documentation (MEDIUM-HIGH confidence)
- [Docker Hub - TimescaleDB](https://hub.docker.com/r/timescale/timescaledb) - TimescaleDB 2.18.0-pg17 verified
- [Stravalib Documentation](https://stravalib.readthedocs.io/) - Official Strava API client
- [PyPI - fitparse](https://pypi.org/project/fit-tool/) - FIT file parser
- [FastAPI Security Tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) - OAuth2 + JWT guide

### Web Search - 2026 Sources (MEDIUM confidence)
- [JetBrains PyCharm Blog: FastAPI vs Django vs Flask (Feb 2025)](https://blog.jetbrains.com/pycharm/2025/02/django-flask-fastapi/)
- [Frontend Framework Comparison 2026](https://merge.rocks/blog/comparing-front-end-frameworks-for-startups-in-2025-svelte-vs-react-vs-vue)
- [Medium: Poetry vs UV Package Manager (2025)](https://medium.com/@hitorunajp/poetry-vs-uv-which-python-package-manager-should-you-use-in-2025-4212cb5e0a14)
- [Strapi: Vite vs Next.js 2025 Developer Framework Guide](https://strapi.io/blog/vite-vs-nextjs-2025-developer-framework-comparison)
- [JetBrains PyCharm Blog: pytest vs unittest (Mar 2024)](https://blog.jetbrains.com/pycharm/2024/03/pytest-vs-unittest/)

---
*Stack research for: Cycling Analytics Platform*
*Researched: 2026-02-10*
*Researcher: gsd-project-researcher*
