"""POST /sources/paste-link — turn a pasted article URL into an attributed brief,
requires_citation always True (blueprint Section 10)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.engine.brief_builder import BriefResult
from app.engine.memory import MemoryStore
from app.models.enums import Format
from app.sources.paste_link import PasteLinkError, build_paste_link_brief, extract_source
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT

router = APIRouter()


class PasteLinkRequest(BaseModel):
    url: str
    format: Format = Format.CAROUSEL


@router.post("/sources/paste-link", response_model=BriefResult)
def paste_link(request: PasteLinkRequest) -> BriefResult:
    try:
        source = extract_source(request.url)
    except PasteLinkError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    memory = MemoryStore().load()
    return build_paste_link_brief(source, WGS_BRAND_KIT, memory, format=request.format)
