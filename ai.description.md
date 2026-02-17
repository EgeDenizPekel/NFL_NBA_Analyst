# NFL/NBA Sports Analysis Chatbot

## What This Is

A local web app that lets users have natural conversations about NFL and NBA sports — upcoming games, player/team stats, historical trends, and comparisons. Responses are data-driven (backed by real stats from APIs) and include inline charts when relevant.

## Tech Stack

- **Frontend**: React + Vite + TypeScript
- **Backend**: Python FastAPI
- **LLM**: Ollama running Llama 3.1 8B locally (no external API keys)
- **NBA data**: `nba_api` Python package + ESPN public endpoints
- **NFL data**: `nfl_data_py` Python package + ESPN public endpoints
- **Charts**: Recharts (rendered inline in chat messages)
- **Streaming**: Server-Sent Events (SSE) for LLM token streaming

## Architecture Overview

The system follows a **context-injection pattern**, not tool-calling:

1. User sends a message via the React chat UI
2. Backend `SportsContextService` analyzes the message using **keyword-based intent detection** (not LLM-based — fast and deterministic)
3. It identifies: sport (NBA/NFL), intent (stats lookup, schedule, standings, comparison), and entities (player/team names via fuzzy matching)
4. Relevant data is fetched from `nba_api`/`nfl_data_py`/ESPN and formatted as concise text
5. This text is injected as a system context message alongside the conversation history into the Ollama LLM call
6. The LLM streams its response back via SSE
7. Frontend accumulates tokens and parses any `|||CHART|||{json}|||END_CHART|||` blocks into inline Recharts components

**Why keyword detection over LLM tool-calling?** Llama 3.1 8B is unreliable at structured tool-calling. Keyword matching is instant, predictable, and sufficient for the intent categories we support.

**Why SSE over WebSocket?** The streaming is unidirectional (server → client). SSE is simpler and works with standard `fetch()` + `ReadableStream`.

## Project Structure

```
backend/                         # Python FastAPI
  main.py                       # App entry, CORS, lifespan (Ollama warmup)
  config.py                     # Settings via pydantic-settings
  routers/
    chat.py                     # POST /api/chat → SSE streaming response
    sports.py                   # GET /api/sports/* data endpoints
    health.py                   # GET /api/health
  services/
    llm_service.py              # Ollama async client, system prompt, streaming
    nba_service.py              # nba_api wrappers (sync, wrapped in asyncio.to_thread)
    nfl_service.py              # nfl_data_py + ESPN wrappers
    sports_context.py           # Intent detection + data orchestration (core logic)
    chart_service.py            # Chart data determination
  models/
    chat.py                     # Pydantic models: ChatRequest, ChatMessage
    sports.py                   # Pydantic models: PlayerStats, TeamInfo, etc.
  utils/
    cache.py                    # In-memory TTL cache
    espn_client.py              # httpx wrapper for ESPN public API

frontend/                        # React + Vite + TypeScript
  src/
    hooks/useChat.ts            # Core hook: message state, SSE streaming, chart parsing
    components/Chat/            # ChatContainer, MessageList, MessageBubble, ChatInput
    components/Charts/          # ChartRenderer, BarChart/LineChart/RadarChart widgets
    components/Layout/          # Header, Sidebar (sport toggle, quick prompts)
    types/                      # TypeScript interfaces for chat and sports domain
```

## Key Files to Understand

- **`backend/services/sports_context.py`** — The "brain". Routes user intent to the right data fetchers. If you're debugging why the LLM lacks context for a query, start here.
- **`backend/services/llm_service.py`** — System prompt lives here. Controls LLM behavior, chart output format, and persona.
- **`frontend/src/hooks/useChat.ts`** — Most complex frontend logic. Manages SSE streaming, message accumulation, and chart extraction from `|||CHART|||` delimiters.
- **`backend/services/nba_service.py`** / **`nfl_service.py`** — Data layer. Note: `nba_api` is synchronous and must be wrapped in `asyncio.to_thread()`.

## Important Patterns

- **`nba_api` is sync** — All calls wrapped in `asyncio.to_thread()` to not block FastAPI's event loop
- **Caching** — In-memory TTL cache (standings: 1hr, scoreboard: 5min, player stats: 30min) to avoid hammering APIs
- **Chart protocol** — LLM embeds `|||CHART|||{"type":"bar","title":"...","data":[...],"xKey":"name","yKeys":["val"]}|||END_CHART|||` in responses. Frontend strips these from text and renders Recharts components. Malformed JSON is silently skipped.
- **Entity extraction** — Player names are fuzzy-matched against cached active player lists using `difflib.get_close_matches`

## Running Locally

Requires three terminals: Ollama (`ollama serve`), backend (`uvicorn main:app --reload --port 8000`), frontend (`npm run dev` at `:5173`). Vite proxies `/api` to the backend.

## Full Specification

See `project.spec.md` for complete implementation details, phase breakdown, ESPN endpoint list, and risk mitigations.
