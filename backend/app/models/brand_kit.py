from pydantic import BaseModel


class MoodPalette(BaseModel):
    primary: str                      # hex — duotone shadow
    secondary: str                    # hex — duotone highlight
    accent: str                       # hex — script word, masthead rule, CTAs


class VoiceRegister(BaseModel):
    poetic: list[str]                 # calm/poetic — quotes, feelings, story/reflection content
    direct: list[str]                 # grounded/direct — research/opinion content


class BrandKit(BaseModel):
    brand_name: str                   # full name, e.g. "Women's Growth Society"
    handle: str                       # e.g. "@womensgrowthsociety" — spelled out ONLY on
                                       # the closing template's footnote, for content that
                                       # circulates outside Instagram
    masthead_short: str                # e.g. "WGS" — appears on every slide's masthead
    niche: str
    audience: str

    voice_traits: list[str]
    voice_samples: VoiceRegister       # two registers — resolved per-post by approach, not one flat list
    forbidden: list[str] = []

    mood_palettes: dict[str, MoodPalette]   # keys: "wisdom" | "bold" | "celebratory"
    text_color: str                    # hex — shared across all moods
    background_color: str              # hex — shared across all moods
    font_heading: str                  # e.g. "Archivo Black"
    font_script: str                   # e.g. "Alex Brush" — one accent word only
    font_body: str                     # e.g. "Inter"

    default_tone: list[str]
    signature_cta: str | None = None
