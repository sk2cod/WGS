"""FastAPI entry point. CORS is restricted to a single configured origin
(FRONTEND_ORIGIN — the Next.js dev server locally, the Vercel domain in
production); tightening this further for prod deploy is Phase 6's job."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.generate import router as generate_router
from app.routes.picks import router as picks_router
from app.routes.sources import router as sources_router
from app.routes.topics import router as topics_router

app = FastAPI(title="Content Studio API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(generate_router)
app.include_router(picks_router)
app.include_router(sources_router)
app.include_router(topics_router)
