from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import chat, health, sports
from services.llm_service import warmup


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        print(f"Warming up Ollama model '{settings.ollama_model}'...")
        await warmup()
        print("Ollama warmup complete.")
    except Exception as e:
        print(f"Ollama warmup failed (is Ollama running?): {e}")
    yield


app = FastAPI(title="NFL/NBA Sports Analyst", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(sports.router)
