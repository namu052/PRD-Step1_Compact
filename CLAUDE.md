# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

"AI 지방세 지식인 APP" — a Korean local tax knowledge assistant with GPKI authentication, AI-powered chat with SSE streaming, source verification, and law/regulation preview. The project is built in 3 steps via prompt files in `md/`.

## Architecture (3-Step Build)

### Step 1: Frontend (`frontend/`)
- **Stack**: Vite + React 18, Tailwind CSS (via `@tailwindcss/vite` plugin), Zustand (state), react-markdown + remark-gfm
- **Mock layer**: MSW (Mock Service Worker) for browser-based API mocking during development
- **Layout**: 50:50 split — left ChatPanel, right PreviewPanel, top TopBar, bottom StatusStepper
- **Key stores**: `authStore.js` (GPKI login state), `chatStore.js` (messages, SSE streaming, sources)
- **SSE parsing**: Done inline in chatStore using `fetch` + `ReadableStream` (not EventSource)
- **No external UI libraries** — Tailwind CSS only

### Step 2: Backend (`backend/`)
- **Stack**: FastAPI + uvicorn, SSE via `sse-starlette`, Pydantic v2 + pydantic-settings
- **Config**: `app/config.py` uses pydantic-settings with `.env` file; `OLTA_SELECTORS` dict for crawler CSS selectors
- **Mock mode flags**: `USE_MOCK_CRAWLER=true` and `USE_MOCK_LLM=true` env vars — all development starts in mock mode
- **Structure**: `app/{routers,services,models,core,prompts}/`, `tests/mocks/`
- **APIs**: `POST /api/auth/gpki`, `GET /api/auth/certs`, `POST /api/auth/logout`, `POST /api/chat` (SSE), `GET /api/preview/{source_id}`
- **Session**: In-memory session management with 30-min timeout auto-cleanup

### Step 3: Verification Pipeline (`backend/app/services/verification/`)
- 2-stage LLM pipeline: Stage 1 (draft) → Stage 2 (source verification + content verification → aggregation → final answer)
- **Models**: `SourceVerification`, `ContentClaim`, `VerificationResult`, `FinalAnswer` (dataclasses in `app/models/verification.py`)
- **SSE stages expand**: crawling → drafting → verifying → finalizing → done (5 steps total)
- **Confidence scoring**: 0.7+ "높음", 0.4+ "보통", <0.4 "낮음" — displayed as badge in frontend

## Common Commands

### Frontend
```bash
cd frontend
npm install
npm run dev          # Dev server at localhost:5173
npm run build        # Production build
```

### Backend
```bash
cd backend
pip install -r requirements.txt
playwright install chromium

# Run server (always use mock mode for development)
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true uvicorn app.main:app --reload --port 8000

# Run tests
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/ -k "not e2e" -v
```

### Integrated Run
Frontend proxy config in `vite.config.js` routes `/api` to `http://localhost:8000`. Run backend and frontend simultaneously. Set `VITE_USE_MOCK !== 'true'` in frontend to disable MSW when using real backend.

## Key Design Decisions

- **Mock-first development**: Every feature works with mock data before real integrations (GPKI, OLTA crawler, OpenAI LLM)
- **SSE over WebSocket**: Chat uses Server-Sent Events with structured event types (`stage_change`, `token`, `sources`, `done`)
- **TODO.md-driven workflow**: Each step maintains its own TODO.md with checkboxes and test results — check and update these as you work
- **GPKI modal blocks usage**: App shows login modal on startup; chat is disabled until authenticated
- **Korean language UI**: All user-facing text is in Korean
- **Source type badge colors**: 법령(blue), 해석례(green), 판례(purple), 훈령(orange)
- **Password "test1234"** is the mock-mode credential for GPKI authentication

## Prompt Files

- `md/CLAUDE_CODE_STEP1_PROMPT.md` — Frontend implementation (5 phases)
- `md/CLAUDE_CODE_STEP2_PROMPT.md` — Backend + crawling + LLM (5 phases)
- `md/CLAUDE_CODE_STEP3_PROMPT.md` — Verification pipeline (5 phases)

Each prompt is self-contained with TODO templates, implementation instructions, and verification checklists. Execute them in order (Step 1 → 2 → 3).
