# NFL/NBA Sports Analysis Chatbot — Project Specification

## Context

Building a web-based sports analysis chatbot for NFL and NBA as a GRAD-5900 class project (+ personal project to continue after). The app lets users have natural conversations about sports — asking about upcoming games, player/team stats, historical trends — and gets back data-driven analysis with inline charts. Designed for a local demo.

## Tech Stack

| Layer | Choice |
|-------|--------|
| Frontend | React + Vite + TypeScript |
| Backend | Python FastAPI |
| LLM | Ollama + Llama 3.1 8B (local, no API costs) |
| NBA Data | `nba_api` (Python) + ESPN public endpoints |
| NFL Data | `nfl_data_py` + ESPN public endpoints |
| Charts | Recharts |
| Streaming | Server-Sent Events (SSE) |
| State Mgmt | React `useState` + custom hooks (no Redux needed) |

## Project Structure

```
NFL_NBA_Analyst/
├── README.md
├── .gitignore
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── main.py                    # FastAPI app, CORS, lifespan
│   ├── config.py                  # pydantic-settings
│   ├── routers/
│   │   ├── chat.py                # POST /api/chat (SSE streaming)
│   │   ├── sports.py              # GET /api/sports/* endpoints
│   │   └── health.py              # GET /api/health
│   ├── services/
│   │   ├── llm_service.py         # Ollama client, system prompt, streaming
│   │   ├── nba_service.py         # nba_api + ESPN NBA wrappers
│   │   ├── nfl_service.py         # nfl_data_py + ESPN NFL wrappers
│   │   ├── sports_context.py      # Intent detection + data orchestrator
│   │   └── chart_service.py       # Chart data determination
│   ├── models/
│   │   ├── chat.py                # ChatRequest, ChatMessage, ChatResponse
│   │   └── sports.py              # PlayerStats, TeamInfo, GamePreview
│   └── utils/
│       ├── cache.py               # TTL in-memory cache
│       └── espn_client.py         # httpx wrapper for ESPN API
├── frontend/
│   ├── package.json
│   ├── vite.config.ts             # Proxy /api → localhost:8000
│   ├── tsconfig.json
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── index.css
│       ├── components/
│       │   ├── Chat/
│       │   │   ├── ChatContainer.tsx
│       │   │   ├── MessageList.tsx
│       │   │   ├── MessageBubble.tsx
│       │   │   ├── ChatInput.tsx
│       │   │   └── StreamingText.tsx
│       │   ├── Charts/
│       │   │   ├── ChartRenderer.tsx
│       │   │   ├── BarChartWidget.tsx
│       │   │   ├── LineChartWidget.tsx
│       │   │   └── RadarChartWidget.tsx
│       │   └── Layout/
│       │       ├── Header.tsx
│       │       ├── Sidebar.tsx
│       │       └── Layout.tsx
│       ├── hooks/
│       │   ├── useChat.ts         # Core: chat state + SSE streaming
│       │   └── useSportsData.ts
│       ├── services/
│       │   └── api.ts
│       ├── types/
│       │   ├── chat.ts
│       │   └── sports.ts
│       └── utils/
│           └── formatters.ts
```

## Architecture & Data Flow

```
User message → Frontend (useChat hook)
  → POST /api/chat with message history + sport hint
  → SportsContextService: keyword-based intent detection
    → Detects: sport, intent (stats/schedule/standings/comparison), entities (player/team names)
    → Fetches relevant data from NBAService / NFLService
    → Formats as concise text context
  → LLMService: injects [system prompt + data context + conversation] → Ollama
  → SSE stream tokens back to frontend
  → Frontend accumulates text, parses |||CHART||| blocks, renders inline Recharts
```

### Key Design Decisions

- **Context injection over tool-calling**: Llama 3.1 8B isn't reliable at tool-calling. Instead, we detect intent with keyword matching (fast, deterministic), pre-fetch data, and inject it as a system context message before the LLM generates.
- **Chart spec via delimiters**: The LLM outputs `|||CHART|||{json}|||END_CHART|||` when charts add value. Frontend parses these out and renders Recharts components. Malformed JSON gracefully degrades (chart doesn't render, text still works).
- **SSE over WebSocket**: Simpler for unidirectional LLM streaming. Standard `fetch()` + `ReadableStream` on the client.
- **`nba_api` is synchronous**: Wrap in `asyncio.to_thread()` to avoid blocking FastAPI's event loop.

## Data Sources

### NBA
- `nba_api` — player career stats, season averages, game logs, league leaders (free, no API key)
- ESPN public API — scoreboard, standings, schedules, news

### NFL
- `nfl_data_py` — play-by-play, weekly/seasonal stats, rosters, schedules
- ESPN public API — live scores, standings, schedules

### ESPN Endpoints (no auth required)
- `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`
- `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams`
- `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/standings`
- `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news`
- `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`
- `https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams`
- `https://site.api.espn.com/apis/site/v2/sports/football/nfl/standings`
- `https://site.api.espn.com/apis/site/v2/sports/football/nfl/news`

### Caching Strategy
In-memory TTL cache — standings 1hr, scoreboard 5min, player stats 30min.

## Implementation Phases

### Phase 1: Backend Skeleton + Ollama Chat
- Init backend: `requirements.txt`, `main.py`, `config.py`, CORS
- `LLMService` with Ollama async streaming
- `ChatRequest`/`ChatMessage` Pydantic models
- `chat.py` router with SSE `StreamingResponse`
- Warmup Ollama model on startup (lifespan handler)
- Verify with `curl`

### Phase 2: Frontend Chat UI
- Scaffold with `npm create vite@latest -- --template react-ts`
- Install `recharts`, `react-markdown`, `uuid`
- `useChat` hook: SSE parsing, message state, chart extraction
- `ChatContainer`, `MessageList`, `MessageBubble`, `ChatInput` components
- Vite proxy config (`/api` → `localhost:8000`)
- Dark sports-themed CSS

### Phase 3: NBA Data Integration
- `NBAService`: wraps `nba_api` (player stats, game logs, leaders) + ESPN (scoreboard, standings)
- `espn_client.py`: shared httpx wrapper
- `SportsContextService`: keyword-based intent detection, entity extraction via fuzzy matching against active player list (`difflib.get_close_matches`)
- `TTLCache`
- Wire into chat route — NBA questions get real stats as LLM context

### Phase 4: NFL Data Integration
- `NFLService`: wraps `nfl_data_py` (seasonal/weekly stats, rosters, schedules) + ESPN
- Extend `SportsContextService` for NFL intents
- Player name matching against roster data

### Phase 5: Charts
- `ChartRenderer`, `BarChartWidget`, `LineChartWidget`, `RadarChartWidget`
- Chart parsing in `useChat` (`|||CHART|||` delimiter extraction)
- `MessageBubble` renders charts inline after text
- Tune system prompt with 2-3 few-shot chart examples

### Phase 6: Polish
- Sidebar: NBA/NFL toggle, suggested quick-prompt questions
- Welcome message with example queries
- Loading states, error handling, empty states
- Upcoming games display in sidebar (`/api/sports/{sport}/scoreboard`)
- Responsive layout, sports-themed styling refinements

## Prerequisites

```bash
# Install Ollama
brew install ollama
ollama serve          # Start server (separate terminal)
ollama pull llama3.1:8b  # ~4.7GB download

# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

## Running the App

```bash
# Terminal 1: Ollama
ollama serve

# Terminal 2: Backend
cd backend && source venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 3: Frontend
cd frontend
npm run dev
# Opens at http://localhost:5173
```

## Verification Plan

1. **Phase 1**: `curl -X POST http://localhost:8000/api/chat -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"Hello"}]}' --no-buffer` — should stream SSE tokens
2. **Phase 2**: Open `http://localhost:5173`, type a message, see streaming response in chat UI
3. **Phase 3**: Ask "How is Jayson Tatum playing this season?" — response should cite real stats from `nba_api`
4. **Phase 4**: Ask "Who are the top NFL QBs?" — response uses `nfl_data_py` data
5. **Phase 5**: Ask "Compare LeBron and Curry" — should produce inline bar/radar chart
6. **Phase 6**: Full demo flow — switch between NBA/NFL, use quick prompts, verify polish

## Known Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| `nba_api` is slow (500ms-2s per call) | `asyncio.to_thread()` + aggressive caching (30min TTL) |
| Llama 3.1 8B may output malformed chart JSON | Lenient parsing — skip chart, text still works. Few-shot examples help. |
| ESPN endpoints are undocumented | Stable for years. Graceful fallback to cached data on error. |
| `nfl_data_py` is archived | Still functional. Swap to `nflreadpy` if needed (same API surface). |
| First Ollama request is slow (model loading) | Warmup request in FastAPI `lifespan` startup handler. |
| LLM hallucinating stats | System prompt instructs: "Use exact numbers from CONTEXT DATA. If data is missing, say so." |
