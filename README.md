# NFL/NBA Sports Analysis Chatbot

A local, full-stack conversational sports analyst. Ask natural-language questions about NFL and NBA players, teams, standings, and live scores — and get data-driven answers streamed in real time, with optional inline charts.

Built as a graduate class project (GRAD-5900, University of Connecticut) and extended as a personal portfolio piece.

---

## What It Does

- **Chat interface** — ask anything: *"How is Jayson Tatum playing this season?"*, *"Compare Patrick Mahomes and Josh Allen"*, *"NBA standings today"*
- **Real-time data** — pulls live standings, scores, and stats from ESPN and basketball-reference.com at query time; no stale training data
- **Inline charts** — bar, line, and radar charts rendered automatically when a visualization adds value (player comparisons, stat breakdowns, trends)
- **Streaming responses** — tokens arrive as the model generates them, like a live typing effect
- **Sport context sidebar** — toggle between NBA and NFL to focus the model and get quick-access prompts and today's scoreboard

---

## Architecture

```
User
 │
 ▼
React frontend (Vite · TypeScript · Recharts)
 │  POST /api/chat  — SSE stream
 ▼
FastAPI backend
 │
 ├── SportsContextService   keyword intent detection → data fetch → context string
 │     ├── NBAService       basketball-reference scraping + nba_api fallback + ESPN
 │     └── NFLService       nfl_data_py (2024 season) + ESPN
 │
 └── LLMService             injects context into system prompt → streams Ollama tokens
       └── Ollama  (llama3.1:8b, running locally)
```

**Key design decisions:**
- **Keyword intent detection** over LLM tool-calling — Llama 3.1 8B is unreliable at structured tool-calling; keyword matching is instant and deterministic
- **SSE over WebSocket** — streaming is unidirectional; SSE works with standard `fetch()` and needs no handshake
- **Context injection** — current-season data is small enough to inject directly into the system prompt; no RAG pipeline needed
- **Chart protocol** — the LLM embeds `|||CHART|||{json}|||END_CHART|||` markers; the frontend strips and renders them via Recharts

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, TypeScript |
| Charts | Recharts |
| Backend | Python 3.11+, FastAPI, uvicorn |
| LLM | Ollama + llama3.1:8b (local — no API key required) |
| NBA data | `nba_api`, basketball-reference scraping (BeautifulSoup + lxml), ESPN public API |
| NFL data | `nfl_data_py` (2024 season), ESPN public API |
| Streaming | Server-Sent Events |
| HTTP client | httpx (async) |
| Config | pydantic-settings |
| Testing | pytest, pytest-asyncio, pytest-mock (117 fast tests) |

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| Ollama | latest |

Install and pull the model:

```bash
# Install Ollama: https://ollama.com/download
ollama pull llama3.1:8b
```

---

## Setup

**Backend**

```bash
cd backend
pip install -r requirements.txt
```

**Frontend**

```bash
cd frontend
npm install
```

**Environment** (optional — defaults shown)

```bash
cp backend/.env.example backend/.env
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.1:8b
```

---

## Running

Open three terminals:

```bash
# 1 — LLM runtime
ollama serve

# 2 — Backend API  (from /backend)
uvicorn main:app --reload --port 8000

# 3 — Frontend dev server  (from /frontend)
npm run dev
```

Open `http://localhost:5173`. The frontend proxies all `/api` requests to `localhost:8000`.

**Sanity check:**

```bash
curl http://localhost:8000/api/health
# {"status":"ok","ollama":"connected"}
```

---

## Testing

All tests live in `backend/tests/`. Run from the `backend/` directory.

```bash
# Fast unit tests only — no network, runs in ~3 s
python3 -m pytest -m "not integration" -v

# Integration tests — real ESPN / basketball-reference / nfl_data_py calls
python3 -m pytest -m integration -v

# Everything
python3 -m pytest -v
```

| File | What it covers |
|------|---------------|
| `test_cache.py` | TTLCache get / set / delete / expiry |
| `test_sports_context.py` | Sport detection, intent routing, leaders category detection |
| `test_nba_service.py` | bref slug generation, HTML parsing, nba_api DataFrame reading, ESPN shaping |
| `test_nfl_service.py` | Roster lookup, stat formatters, nfl_data_py DataFrame contracts, ESPN shaping |

---

## Example Queries

| Query | What happens |
|-------|-------------|
| *"How is LeBron James playing this season?"* | Scrapes basketball-reference → injects stats → LLM summarizes with optional bar chart |
| *"Compare Jalen Hurts and Lamar Jackson"* | Fetches both from nfl_data_py → radar chart comparing key QB stats |
| *"NBA standings today"* | Calls ESPN standings API → LLM formats conference tables |
| *"Top rushers in the NFL this season"* | Sorts nfl_data_py by rushing yards → LLM lists leaders with bar chart |
| *"NBA scores today"* | Calls ESPN scoreboard → LLM reports live/final scores |

---

## Project Structure

```
NFL_NBA_Analyst/
├── backend/
│   ├── main.py                  # FastAPI app, CORS, lifespan (Ollama warmup)
│   ├── config.py                # pydantic-settings (OLLAMA_BASE_URL, OLLAMA_MODEL)
│   ├── requirements.txt
│   ├── routers/
│   │   ├── chat.py              # POST /api/chat — SSE streaming
│   │   ├── sports.py            # GET /api/sports/{sport}/scoreboard|standings
│   │   └── health.py            # GET /api/health
│   ├── services/
│   │   ├── sports_context.py    # Intent detection + context orchestration
│   │   ├── llm_service.py       # System prompt, Ollama client, SSE streaming
│   │   ├── nba_service.py       # NBA data (bref + nba_api + ESPN)
│   │   └── nfl_service.py       # NFL data (nfl_data_py + ESPN)
│   ├── utils/
│   │   ├── cache.py             # In-memory TTL cache singleton
│   │   └── espn_client.py       # Generic ESPN httpx helper
│   └── tests/                   # 117 fast + 8 integration tests
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── Chat/            # ChatContainer, MessageList, MessageBubble, ChatInput
    │   │   ├── Charts/          # BarChartWidget, LineChartWidget, RadarChartWidget
    │   │   └── Layout/          # Layout, Header, Sidebar
    │   ├── hooks/
    │   │   ├── useChat.ts       # SSE streaming, message state, chart extraction
    │   │   └── useSportsData.ts # Live scoreboard fetch
    │   └── types/
    │       └── chat.ts          # Message, ChartData, Sport types
    └── README.md                # Frontend-specific docs
```

---

## Known Limitations

- **NFL data is season-bound** — `nfl_data_py` loads the 2024 regular season; live play-by-play and postseason data are not included
- **basketball-reference rate limiting** — bref occasionally blocks scrapers; the `nba_api` fallback handles this automatically
- **LLM response quality** — Llama 3.1 8B occasionally drifts from the system prompt on complex multi-player comparisons; upgrading to a larger model improves this significantly
- **No user accounts or history persistence** — conversation state lives in React component memory and resets on page refresh
