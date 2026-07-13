"""Image adapter — wraps GPT Image 2 today; swap freely behind this interface
(blueprint Section 9: the provider landscape is fast-moving and cheap, the pipeline
shouldn't have to change when it does)."""

from __future__ import annotations

import base64

from openai import OpenAI

from app.config import get_settings


class ImageProvider:
    """Wraps GPT Image 2. `generate` returns raw image bytes; duotoning happens
    afterward in `providers/duotone.py`, kept as a separate deterministic step."""

    def __init__(self, client: OpenAI | None = None):
        settings = get_settings()
        self._client = client or OpenAI(api_key=settings.openai_api_key)
        self._model = settings.image_model

    def generate(self, *, prompt: str, size: str, quality: str) -> bytes:
        response = self._client.images.generate(
            model=self._model,
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )
        b64 = response.data[0].b64_json
        if not b64:
            raise RuntimeError("image provider returned no image data")
        return base64.b64decode(b64)
