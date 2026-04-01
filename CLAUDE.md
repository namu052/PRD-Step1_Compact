# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI 지방세 지식인 APP — a full-stack application that helps Korean government officials answer local tax (지방세) questions. It crawls the OLTA (지방세법령포털) website, performs LLM-based analysis with multi-round verification, and provides evidence-based answers with source citations via SSE streaming.

## Build & Development Commands

### Frontend (run from `frontend/`)
- `npm install` — install dependencies
- `npm run dev` — Vite dev server (proxies `/api/*` to backend at `127.0.0.1:8000`)
- `npm run build` — production build to `dist/`
- `npm run lint` — ESLint check

### Backend (run from `backend/`)
- `pip install -r requirements.txt` — install dependencies (or use `uv`)
- `uvicorn app.main:app --reload` — start FastAPI dev server on port 8000
- `pytest tests/ -v` — run all tests
- `pytest tests/test_chat_pipeline.py -v` — run a single test file
- Backend requires `.env` file (see `.env.example` for variables, notably `OPENAI_API_KEY`)

## Architecture

### Stack
- **Frontend**: React 19 + Vite 8 + Zustand (state) + Tailwind CSS 4 + MSW (mock API)
- **Backend**: FastAPI + Playwright (OLTA scraping) + OpenAI API (GPT-4o) + FAISS (embeddings)
- **Communication**: SSE streaming (`EventSource`) for real-time token-by-token responses

### Frontend Structure (`frontend/src/`)
- **Stores** (Zustand): `authStore.js` (GPKI auth/session), `chatStore.js` (messages, streaming, sources, confidence)
- **Layout**: 50:50 split — `ChatPanel` (left) + `PreviewPanel` (right, source cards)
- **SSE hook**: `hooks/useSSE.js` consumes streaming events from backend
- **Mock mode**: MSW enabled when `VITE_USE_MOCK` is set; handlers in `mocks/handlers.js`
- **Vite plugin**: `gpkiPlugin()` in `vite.config.js` reads GPKI certificates from local filesystem

### Backend Pipeline (`backend/app/`)
The chat endpoint (`routers/chat.py`, `/api/chat`) orchestrates a multi-stage pipeline via SSE:

1. **Search Planning** (`services/search_service.py`) — LLM extracts search keywords from user question
2. **Web Crawling** (`services/crawler_service.py`) — Playwright scrapes OLTA; falls back to mock data if unreachable
3. **Embedding & Ranking** (`services/embedding_service.py`) — FAISS indexes documents, semantic similarity ranking
4. **Evidence Grouping** (`services/evidence_group_service.py`) — clusters similar sources
5. **Draft Generation** (`services/llm_service.py`) — creates initial answer with cited sources
6. **Verification** (`services/verification/`) — multi-round verification cycle:
   - `source_verifier.py` validates source references
   - `content_verifier.py` checks factual claims against sources
   - `grouped_answer_verifier.py` validates evidence slots
   - `verification_aggregator.py` aggregates confidence scores
7. **Final Generation** (`services/verification/final_generator.py`) — refines answer based on verification feedback

SSE event types: `stage_change`, `token`, `sources`, `confidence`, `final_answer`, `system_message`

Pipeline stages shown in UI: crawling → drafting → verifying → finalizing → done

### Configuration
- Backend config: `app/config.py` (Pydantic Settings) — all magic numbers and thresholds are centralized here
- LLM prompts: `app/prompts/` — separate prompt template files per stage
- Sessions: in-memory storage via `core/session_manager.py` (no database)

## Code Conventions

- 2-space indentation, semicolon-free JavaScript, ES modules throughout
- Components: PascalCase (`ChatPanel.jsx`), Stores: camelCase + `Store` suffix
- Backend services: snake_case with `_service.py` suffix
- Prompt constants: SCREAMING_SNAKE_CASE
- Keep feature code grouped by domain (`auth/`, `chat/`, `layout/`, `preview/`)
- Run `npm run lint` from `frontend/` before committing frontend changes

## Testing

- **Backend**: pytest + pytest-asyncio; fixtures and mocks in `tests/mocks/`
- **Frontend**: No automated tests; verify via lint + build + manual flows described in `frontend/TODO.md`
