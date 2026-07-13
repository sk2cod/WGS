"""GET /picks — today's 3 daily picks, computed once per day and cached (a batch job
or the first request of the day triggers computation; every later read is a cache
hit). POST /picks/reroll swaps one pick, rate-limited to MAX_REROLLS_PER_DAY."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.engine.memory import MemoryStore
from app.engine.selector import (
    DailyPicksResult,
    PicksStore,
    RerollError,
    get_or_compute_daily_picks,
    reroll_pick,
)
from app.providers.llm import LLMProvider
from app.taxonomy.loader import get_topics
from app.taxonomy.wgs_brand_kit import get_brand_kit

router = APIRouter()


class RerollRequest(BaseModel):
    pick_index: int


@router.get("/picks", response_model=DailyPicksResult)
def get_picks() -> DailyPicksResult:
    return get_or_compute_daily_picks(
        topics=list(get_topics()),
        memory=MemoryStore().load(),
        brand_kit=get_brand_kit(),
        llm=LLMProvider(),
        store=PicksStore(),
        target_date=date.today(),
    )


@router.post("/picks/reroll", response_model=DailyPicksResult)
def reroll(request: RerollRequest) -> DailyPicksResult:
    try:
        return reroll_pick(
            topics=list(get_topics()),
            memory=MemoryStore().load(),
            brand_kit=get_brand_kit(),
            llm=LLMProvider(),
            store=PicksStore(),
            target_date=date.today(),
            pick_index=request.pick_index,
        )
    except RerollError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
