from app.db import supabase as db
from app.models.brand_kit import BrandKit

# Locked WGS values — Section 6 of implementation-guide.md / Section 4 of the blueprint.
# Mirrors frontend/lib/wgs-brand-kit.ts. Also doubles as the seed row: get_brand_kit()
# upserts this into Supabase the first time the table is empty, so production reads
# come from the database from then on without a separate migration/seed script.
WGS_BRAND_KIT = BrandKit.model_validate(
    {
        "brand_name": "Women's Growth Society",
        "handle": "@womensgrowthsociety",
        "masthead_short": "WGS",
        "niche": (
            "Practical emotional intelligence and confidence-building for women "
            "unlearning people-pleasing and navigating career and self-worth."
        ),
        "audience": (
            "Women in their 20s-40s building a career while learning to trust "
            "themselves, and craving steady, honest encouragement over empty positivity."
        ),
        "voice_traits": ["supportive", "trusted", "encouraging", "calm", "grounded-in-facts"],
        "voice_samples": {
            "poetic": [
                "You don't have to shrink to keep the peace. Some rooms were never meant to hold all of you.",
                "The tears you're hiding today are just proof you're finally listening to yourself.",
                "Growth doesn't announce itself. It just quietly becomes the way you breathe.",
                "You're allowed to outgrow people who only ever loved the smaller version of you.",
                "Some days strength looks like getting up. Other days, it looks like finally resting.",
            ],
            "direct": [
                "Research shows women get interrupted more in meetings than men. Naming it doesn't fix it — but it's the first step.",
                "Confidence isn't a feeling you wait for. It's a skill you build one uncomfortable conversation at a time.",
                "You don't need permission to negotiate your salary. You need the numbers, and the nerve to say them out loud.",
                "Boundaries aren't about being difficult. They're about being clear enough that no one has to guess.",
                "Burnout isn't a personal failing. It's what happens when the workload outpaces the support.",
            ],
        },
        "forbidden": [
            "preachy",
            "bossy",
            "negative",
            "overly corporate",
            "fake positivity",
            "clickbait",
            "hustle-mindset language",
            "engagement-bait CTAs (e.g. 'comment ❤️ if...')",
        ],
        "mood_palettes": {
            "wisdom": {"primary": "#4B3A6E", "secondary": "#F3EEF9", "accent": "#8A63D2"},
            "bold": {"primary": "#8C3B2E", "secondary": "#F7E9DE", "accent": "#D9643F"},
            "celebratory": {"primary": "#6E4F17", "secondary": "#FCEDB8", "accent": "#E8A23D"},
        },
        "text_color": "#241C33",
        "background_color": "#FAF7FC",
        "font_heading": "Archivo Black",
        "font_script": "Alex Brush",
        "font_body": "Inter",
        "default_tone": ["warm", "encouraging"],
        "signature_cta": "Follow us for daily reminders that help you grow.",
    }
)


def get_brand_kit() -> BrandKit:
    """Production accessor: reads the one brand_kit row from Supabase, seeding it from
    WGS_BRAND_KIT on first call if the table is still empty."""
    existing = db.fetch_brand_kit()
    if existing is not None:
        return existing
    db.upsert_brand_kit(WGS_BRAND_KIT)
    return WGS_BRAND_KIT
