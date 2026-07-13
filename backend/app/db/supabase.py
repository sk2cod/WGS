"""Supabase client + queries (Section 9 of implementation-guide.md).

Thin wrapper around the `supabase-py` client. Not yet wired into `engine/memory.py`
or `providers/duotone.py` as their backing store — those stay file-backed until a
later phase swaps them in behind the same interface. This module exists so the
tables/bucket created by `schema.sql` have a typed access point ready to use.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings
from app.models.brand_kit import BrandKit
from app.models.memory import MemoryRecord


@lru_cache(maxsize=1)
def get_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def fetch_brand_kit() -> BrandKit | None:
    res = get_client().table("brand_kit").select("*").limit(1).execute()
    if not res.data:
        return None
    row = res.data[0]
    return BrandKit(
        brand_name=row["brand_name"],
        handle=row["handle"],
        masthead_short=row["masthead_short"],
        niche=row["niche"],
        audience=row["audience"],
        voice_traits=row["voice_traits"],
        voice_samples={
            "poetic": row["voice_samples_poetic"],
            "direct": row["voice_samples_direct"],
        },
        forbidden=row["forbidden"],
        mood_palettes=row["mood_palettes"],
        text_color=row["text_color"],
        background_color=row["background_color"],
        font_heading=row["font_heading"],
        font_script=row["font_script"],
        font_body=row["font_body"],
        default_tone=row["default_tone"],
        signature_cta=row.get("signature_cta"),
    )


def upsert_brand_kit(kit: BrandKit) -> None:
    get_client().table("brand_kit").upsert(
        {
            "brand_name": kit.brand_name,
            "handle": kit.handle,
            "masthead_short": kit.masthead_short,
            "niche": kit.niche,
            "audience": kit.audience,
            "voice_traits": kit.voice_traits,
            "voice_samples_poetic": kit.voice_samples.poetic,
            "voice_samples_direct": kit.voice_samples.direct,
            "forbidden": kit.forbidden,
            "mood_palettes": {k: v.model_dump() for k, v in kit.mood_palettes.items()},
            "text_color": kit.text_color,
            "background_color": kit.background_color,
            "font_heading": kit.font_heading,
            "font_script": kit.font_script,
            "font_body": kit.font_body,
            "default_tone": kit.default_tone,
            "signature_cta": kit.signature_cta,
        }
    ).execute()


def fetch_memory() -> list[MemoryRecord]:
    res = get_client().table("memory").select("*").execute()
    return [MemoryRecord.model_validate(row) for row in res.data]


def append_memory(record: MemoryRecord) -> None:
    get_client().table("memory").insert(record.model_dump(mode="json")).execute()


def get_cached_hero_url(cache_key: str) -> str | None:
    res = (
        get_client()
        .table("image_cache")
        .select("storage_url")
        .eq("cache_key", cache_key)
        .limit(1)
        .execute()
    )
    return res.data[0]["storage_url"] if res.data else None


def cache_hero_url(
    cache_key: str, keyword: str, shadow_hex: str, highlight_hex: str, storage_url: str
) -> None:
    get_client().table("image_cache").upsert(
        {
            "cache_key": cache_key,
            "keyword": keyword,
            "shadow_hex": shadow_hex,
            "highlight_hex": highlight_hex,
            "storage_url": storage_url,
        }
    ).execute()


def upload_hero_image(path: str, data: bytes) -> str:
    """Upload a duotoned hero PNG to the `heroes` bucket and return its public URL."""
    client = get_client()
    client.storage.from_("heroes").upload(
        path, data, {"content-type": "image/png", "upsert": "true"}
    )
    return client.storage.from_("heroes").get_public_url(path)
