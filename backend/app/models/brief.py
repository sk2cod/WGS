from datetime import datetime

from pydantic import BaseModel

from .enums import Approach, Format, Sensitivity


class Source(BaseModel):
    title: str
    author: str | None = None
    url: str | None = None
    excerpt: str                      # only citable text
    retrieved_at: datetime


class ContentBrief(BaseModel):
    topic_id: str
    topic_name: str
    angle: str
    approach: Approach
    goal: str                         # educate | inspire | reflect | inform
    mood: str = "wisdom"               # wisdom | bold | celebratory — tagged w/ the angle

    format: Format
    slide_count: int                   # 1 for single image; 3-4 for carousel
    tone: list[str]
    brand_voice_samples: list[str]
    signature_cta: str | None = None

    requires_citation: bool = False
    sensitivity: Sensitivity = Sensitivity.NORMAL
    sources: list[Source] = []

    hero_image_prompt: str
    max_words_per_slide: int = 30
