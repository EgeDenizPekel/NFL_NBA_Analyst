# Agent Instructions — NFL/NBA Sports Analysis Chatbot

## Project Identity

- **Name**: NFL/NBA Sports Analysis Chatbot
- **Type**: Local full-stack web app (class project + personal extension)
- **Purpose**: Conversational sports analysis — users ask natural-language questions about NFL/NBA games, players, stats, and trends; the system responds with data-driven answers and optional inline charts.
- **Status**: Phases 1–6 complete — NBA/NFL data pipelines, SSE streaming, Recharts, Sidebar with sport toggle and quick prompts.

## Folder Structure

```
NFL_NBA_Analyst/
├── agent.instructions.md          # This file — project context for agents
├── ai.description.md              # High-level system description and architecture overview
├── project.spec.md                # Full implementation spec with phases, endpoints, risks
├── backend/                       # Python FastAPI backend
│   ├── requirements.txt           # fastapi, uvicorn, httpx, pydantic-settings
│   ├── .env.example               # OLLAMA_BASE_URL, OLLAMA_MODEL
│   ├── main.py                    # App entry, CORS, lifespan (Ollama warmup)
│   ├── config.py                  # pydantic-settings config
│   ├── routers/
│   │   ├── chat.py                # POST /api/chat — SSE streaming response
│   │   ├── sports.py              # GET /api/sports/* — stubs for Phase 3/4
│   │   └── health.py              # GET /api/health (checks Ollama connectivity)
│   ├── services/
│   │   ├── llm_service.py         # Ollama async client, system prompt, stream_chat(), warmup()
│   │   ├── nba_service.py         # bref scraping (slugs 01-05) + nba_api fallback + ESPN wrappers
│   │   ├── nfl_service.py         # nfl_data_py seasonal/roster + ESPN NFL wrappers
│   │   ├── sports_context.py      # Sport + intent detection; NBA and NFL context builders
│   │   └── chart_service.py       # (planned Phase 5)
│   ├── models/
│   │   ├── chat.py                # Pydantic: ChatMessage, ChatRequest
│   │   └── sports.py              # (planned Phase 5) PlayerStats, TeamInfo, GamePreview
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py            # sys.path fix; usage docs for fast vs integration tests
│   │   ├── test_cache.py          # TTLCache unit tests (9 tests)
│   │   ├── test_nba_service.py    # NBAService unit + integration tests (35 fast, 4 integration)
│   │   ├── test_nfl_service.py    # NFLService unit + integration tests (27 fast, 4 integration)
│   │   └── test_sports_context.py # Intent/sport/entity detection tests (31 tests)
│   ├── pytest.ini                 # asyncio_mode=auto; integration marker definition
│   └── utils/
│       ├── cache.py               # In-memory TTL cache singleton
│       └── espn_client.py         # Generic httpx ESPN helper (used by sports.py router)
└── frontend/                      # (planned Phase 2) React + Vite + TypeScript frontend
    ├── package.json
    ├── vite.config.ts             # Proxies /api → localhost:8000
    ├── tsconfig.json
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── index.css
        ├── components/
        │   ├── Chat/              # ChatContainer, MessageList, MessageBubble, ChatInput, StreamingText
        │   ├── Charts/            # ChartRenderer (type router), BarChartWidget, LineChartWidget, RadarChartWidget (with stat normalisation)
        │   └── Layout/            # Header, Sidebar, Layout
        ├── hooks/
        │   ├── useChat.ts         # Core: SSE streaming, message state, chart parsing; exposes sport/setSport
        │   └── useSportsData.ts   # Fetches /api/sports/{sport}/scoreboard; cancels on cleanup
        ├── services/
        │   └── api.ts
        ├── types/
        │   ├── chat.ts
        │   └── sports.ts
        └── utils/
            └── formatters.ts
```

## Domain / Topic Overview

- **NBA data**: `nba_api` package (player career stats, season averages, game logs, league leaders) + ESPN public endpoints (scoreboard, standings, news)
- **NFL data**: `nfl_data_py` package (play-by-play, weekly/seasonal stats, rosters, schedules) + ESPN endpoints
- **LLM**: Ollama running `llama3.1:8b` locally — no API keys, no cost
- **Context injection pattern**: Intent detected via keyword matching → data fetched → injected as system context before LLM generates. Not tool-calling (Llama 3.1 8B is unreliable at structured tool-calling).
- **Chart protocol**: LLM embeds `|||CHART|||{json}|||END_CHART|||` in responses. Frontend strips and renders Recharts components. Malformed JSON is silently skipped.

## Tech Stack & Tooling

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, TypeScript |
| Backend | Python 3.11+, FastAPI, uvicorn |
| LLM | Ollama + llama3.1:8b (local) |
| NBA Data | `nba_api` (player lookup + fallback stats), basketball-reference scraping, ESPN public API |
| NFL Data | `nfl_data_py` (seasonal/roster data), ESPN public API |
| Charts | Recharts |
| Streaming | Server-Sent Events (SSE) |
| HTTP client | httpx (async, backend) |
| Validation | pydantic-settings (backend config), Pydantic v2 (models) |
| State | React useState + custom hooks (no Redux) |

## Implementation Phases

1. **Phase 1** ✅ — Backend skeleton + Ollama streaming (FastAPI, LLMService, SSE chat route)
2. **Phase 2** ✅ — Frontend chat UI (Vite scaffold, useChat hook, SSE parsing, MessageBubble)
3. **Phase 3** ✅ — NBA data integration (NBAService, SportsContextService, caching, tests)
4. **Phase 4** ✅ — NFL data integration (NFLService, extend SportsContextService, tests)
5. **Phase 5** ✅ — Charts (BarChartWidget, LineChartWidget, RadarChartWidget, system prompt tuning)
6. **Phase 6** ✅ — Polish (Sidebar with sport toggle + quick prompts + scoreboard, loading dots, responsive layout)

## Data Flow (Request Lifecycle)

1. User sends a message via the React chat UI
2. `useChat` hook POSTs message history + sport hint to `POST /api/chat`
3. `SportsContextService` runs keyword-based intent detection — identifies sport (NBA/NFL), intent type (stats/schedule/standings/comparison), and entities (player/team names via `difflib.get_close_matches` against cached active player/roster lists)
4. Relevant data is fetched from `nba_api` / `nfl_data_py` / ESPN and formatted as concise text
5. `LLMService` injects `[system prompt + data context + conversation history]` into Ollama
6. Ollama streams tokens back via SSE (`StreamingResponse`)
7. Frontend accumulates tokens, parses `|||CHART|||{json}|||END_CHART|||` blocks, and renders inline Recharts components

## Design Rationale

- **Keyword detection over LLM tool-calling**: Llama 3.1 8B is unreliable at structured tool-calling. Keyword matching is instant, predictable, and sufficient for the intent categories supported.
- **SSE over WebSocket**: Streaming is unidirectional (server → client). SSE is simpler and works with standard `fetch()` + `ReadableStream` — no WebSocket handshake overhead.
- **Context injection over RAG**: Data sets are small enough (current season stats, today's scoreboard) that full pre-fetch + injection is simpler and more reliable than a retrieval pipeline.

## Key Files

| File | Role |
|------|------|
| `backend/services/sports_context.py` | Core orchestrator — routes user intent to the right data fetchers. First place to debug missing LLM context. |
| `backend/services/llm_service.py` | System prompt, Ollama async client, SSE streaming logic. Chart output format and LLM persona live here. |
| `backend/services/nba_service.py` | `nba_api` wrappers (sync, must use `asyncio.to_thread()`) + ESPN NBA endpoints. |
| `backend/services/nfl_service.py` | `nfl_data_py` + ESPN NFL wrappers. |
| `frontend/src/hooks/useChat.ts` | Most complex frontend file — SSE parsing, message accumulation, `|||CHART|||` extraction. |

## Testing

All tests live in `backend/tests/`. Run from `backend/` directory.

```bash
# Fast tests only (no network — runs in ~3s)
python3 -m pytest -m "not integration" -v

# Integration tests (real ESPN + bref + nfl_data_py calls — slow)
python3 -m pytest -m integration -v

# All tests
python3 -m pytest -v
```

| File | What it tests |
|------|--------------|
| `test_cache.py` | TTLCache get/set/delete/expiry |
| `test_nba_service.py` | bref slug generation, player lookup, stat formatting, ESPN response shaping, fallback paths |
| `test_nfl_service.py` | roster lookup, QB/RB/WR stat formatting, ESPN response shaping, cache |
| `test_sports_context.py` | Sport detection, intent detection, NBA/NFL leaders category detection |

Bugs caught by tests so far:
- `_detect_intent`: NEWS was checked before PREDICTION, causing prediction queries with "title" to misroute
- `NFL_STAT_PATTERNS`: frozenset iteration order caused "yards" (in passing key) to match receiving/rushing queries
- `NFL_STAT_PATTERNS`: "reception" substring matched before more-specific "receptions" key
- `nfl_service._load_rosters`: called `nfl.import_rosters()` which doesn't exist in nfl_data_py 0.3.x; correct function is `import_seasonal_rosters()`
- Package conflict: `nfl_data_py` requires `pandas<2.0`; `nba_api` declares `pandas>=2.1` but works fine on 1.5.3 — keep pandas pinned at 1.5.x

## Agent Behavior Guidance

- **`nba_api` is synchronous** — always wrap calls in `asyncio.to_thread()` inside async FastAPI handlers
- **Entity extraction**: player/team names matched via `difflib.get_close_matches` against cached active player lists (NBA) and roster data (NFL)
- ESPN endpoints are undocumented but stable; add graceful error handling/fallback to cached data
- Caching is critical for performance: standings 1hr, scoreboard 5min, player stats 30min
- Do not use LLM tool-calling — keyword-based intent detection only
- Frontend chart parsing must be lenient: skip malformed JSON, never break the text display
- **RadarChartWidget** pivots player-row data → stat-row data and normalises each stat to 0–100 per-stat-max so disparate magnitudes (28 PPG vs 0.6 BPG) render meaningfully. Custom tooltip restores original values.
- **Chart type guide**: bar = rankings or single-player breakdown; radar = multi-stat player comparison; line = trends over time (game logs)
- System prompt has 3 concrete few-shot chart examples; this is the primary lever for chart quality
- System prompt must instruct LLM: "Use exact numbers from CONTEXT DATA. If data is missing, say so." (prevents hallucinated stats)
- Run order: `ollama serve` → `uvicorn main:app --reload --port 8000` → `npm run dev` (frontend at `:5173`, proxies `/api` to `:8000`)
