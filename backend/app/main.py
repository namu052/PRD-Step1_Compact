from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.session_manager import session_manager
from app.routers import auth, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await session_manager.cleanup_expired()


app = FastAPI(title="AI 지방세 지식인 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
