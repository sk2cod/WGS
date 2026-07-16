"""Supabase client + queries (Section 9 of implementation-guide.md).

Thin wrapper around the `supabase-py` client. Backs `engine/memory.py` and
`taxonomy/wgs_brand_kit.get_brand_kit()` in production. `providers/duotone.py`'s hero
cache stays file-backed for now — the image_cache table/functions here exist for when
that gets wired in too.
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
    """Update the one brand_kit row if it exists; insert only if the table is
    genuinely empty (the seed-on-empty case, taxonomy/wgs_brand_kit.get_brand_kit()).

    `BrandKit` carries no `id` field, and Supabase's `.upsert()` with no `id` in the
    payload and no existing value to conflict on silently INSERTs a new row instead
    of updating — confirmed live (logbook #35): the first real caller other than the
    seed-on-empty path (routes/export.py's voice-compounding write) produced a
    second, duplicate brand_kit row rather than updating the existing one. Looking
    the current row's id up fresh and updating by it, instead of upserting blind,
    is what makes this correct regardless of caller. `brand_kit_singleton_idx`
    (schema.sql) is the DB-level backstop in case this ever regresses."""
    client = get_client()
    payload = {
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
    existing = client.table("brand_kit").select("id").limit(1).execute()
    if existing.data:
        client.table("brand_kit").update(payload).eq("id", existing.data[0]["id"]).execute()
    else:
        client.table("brand_kit").insert(payload).execute()


def fetch_memory() -> list[MemoryRecord]:
    res = get_client().table("memory").select("*").execute()
    return [MemoryRecord.model_validate(row) for row in res.data]


def fetch_memory_by_id(record_id: str) -> MemoryRecord | None:
    res = get_client().table("memory").select("*").eq("id", record_id).limit(1).execute()
    if not res.data:
        return None
    return MemoryRecord.model_validate(res.data[0])


def append_memory(record: MemoryRecord) -> None:
    get_client().table("memory").insert(record.model_dump(mode="json")).execute()


def update_memory(record: MemoryRecord) -> None:
    get_client().table("memory").update(record.model_dump(mode="json")).eq("id", record.id).execute()


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
