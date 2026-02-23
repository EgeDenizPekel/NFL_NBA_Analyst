# NFL/NBA Sports Analyst — Frontend

React + TypeScript + Vite frontend for the NFL/NBA Sports Analysis Chatbot. Provides a conversational UI that streams responses from a local FastAPI/Ollama backend and renders inline Recharts visualizations.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 18 |
| Build tool | Vite |
| Language | TypeScript |
| Charts | Recharts |
| Streaming | Server-Sent Events via `fetch` + `ReadableStream` |
| Styling | Plain CSS (CSS custom properties, dark theme) |

## Prerequisites

- Node.js 18+
- The backend running at `http://localhost:8000` (see `../backend/`)

## Getting Started

```bash
npm install
npm run dev
```

Opens at `http://localhost:5173`. All `/api` requests are proxied to `http://localhost:8000` via `vite.config.ts`.

## Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server with HMR |
| `npm run build` | Type-check and build for production (`dist/`) |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | Run ESLint |

## Project Structure

```
src/
├── App.tsx                        # Root component — wires useChat, Layout, ChatContainer
├── main.tsx                       # React entry point
├── index.css                      # Global styles and CSS custom properties
├── components/
│   ├── Chat/
│   │   ├── ChatContainer.tsx      # Composes MessageList + ChatInput + error banner
│   │   ├── MessageList.tsx        # Scrollable message feed; welcome screen when empty
│   │   ├── MessageBubble.tsx      # Single message — user bubble, assistant markdown, charts
│   │   ├── ChatInput.tsx          # Auto-growing textarea + send button
│   │   └── StreamingText.tsx      # Renders accumulating text with blinking cursor
│   ├── Charts/
│   │   ├── ChartRenderer.tsx      # Routes chart.type → correct widget
│   │   ├── BarChartWidget.tsx     # Recharts BarChart; supports multiple yKeys (grouped bars)
│   │   ├── LineChartWidget.tsx    # Recharts LineChart; monotone curves with dot markers
│   │   └── RadarChartWidget.tsx   # Recharts RadarChart; normalises stats to 0–100 per-stat-max
│   └── Layout/
│       ├── Layout.tsx             # Page shell — Header + Sidebar + main content slot
│       ├── Header.tsx             # App title bar + New Chat button
│       └── Sidebar.tsx            # Sport toggle, quick prompts, today's scoreboard
├── hooks/
│   ├── useChat.ts                 # SSE streaming, message state, chart extraction, sport state
│   └── useSportsData.ts           # Fetches /api/sports/{sport}/scoreboard on sport change
├── services/
│   └── api.ts                     # (reserved for future API helpers)
├── types/
│   ├── chat.ts                    # Message, ChartData, Sport types
│   └── sports.ts                  # (reserved for future sports data types)
└── utils/
    └── formatters.ts              # (reserved for future formatting helpers)
```

## Key Concepts

**SSE streaming** — `useChat` opens a `fetch` stream to `POST /api/chat`, reads newline-delimited `data: {...}` events, and accumulates tokens into the assistant message in real time.

**Chart protocol** — The LLM embeds `|||CHART|||{json}|||END_CHART|||` markers in its response. Once the stream finishes, `useChat` extracts and parses these blocks. Malformed JSON is silently skipped so a bad chart never breaks the text display.

**Radar chart normalisation** — `RadarChartWidget` pivots player-row data into stat-row format (required by Recharts `RadarChart`) and scales each stat to 0–100 relative to the per-stat maximum. A custom tooltip restores the original values on hover, so disparate magnitudes (e.g. 28 PPG vs 0.6 BPG) render meaningfully on the same axis.

**Sport context** — The `Sidebar` sport toggle sets the active sport (`nba` | `nfl` | `null`) in `useChat`, which is sent with every chat request so the backend can narrow its intent detection.
