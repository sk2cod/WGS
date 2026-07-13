import json
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

import app.sources.paste_link as paste_link_module
from app.engine.brief_builder import BriefResult
from app.models.brief import Source
from app.models.enums import Approach, Format
from app.models.memory import MemoryRecord
from app.sources.paste_link import PasteLinkError, build_paste_link_brief, extract_source
from app.taxonomy.wgs_brand_kit import WGS_BRAND_KIT


class _FakeLLM:
    def __init__(self, response: str):
        self._response = response
        self.prompts: list[str] = []

    def complete(self, *, tier, system, prompt, max_tokens, cache=True):
        self.prompts.append(prompt)
        return self._response


def test_extract_source_builds_source_from_article(monkeypatch):
    monkeypatch.setattr(paste_link_module.trafilatura, "fetch_url", lambda url: "<html>fake</html>")
    monkeypatch.setattr(
        paste_link_module.trafilatura, "extract", lambda html: "The extracted article body."
    )
    monkeypatch.setattr(
        paste_link_module.trafilatura,
        "extract_metadata",
        lambda html, default_url=None: SimpleNamespace(
            title="A New Law Affecting Women", author="Jane Reporter"
        ),
    )

    source = extract_source("https://example.com/article")
    assert source.title == "A New Law Affecting Women"
    assert source.author == "Jane Reporter"
    assert source.url == "https://example.com/article"
    assert source.excerpt == "The extracted article body."
    assert source.retrieved_at.tzinfo is not None


def test_extract_source_raises_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(paste_link_module.trafilatura, "fetch_url", lambda url: None)
    with pytest.raises(PasteLinkError):
        extract_source("https://example.com/dead-link")


def test_extract_source_raises_when_no_extractable_text(monkeypatch):
    monkeypatch.setattr(paste_link_module.trafilatura, "fetch_url", lambda url: "<html></html>")
    monkeypatch.setattr(paste_link_module.trafilatura, "extract", lambda html: None)
    with pytest.raises(PasteLinkError):
        extract_source("https://example.com/empty")


def test_extract_source_falls_back_to_url_when_no_metadata(monkeypatch):
    monkeypatch.setattr(paste_link_module.trafilatura, "fetch_url", lambda url: "<html>fake</html>")
    monkeypatch.setattr(paste_link_module.trafilatura, "extract", lambda html: "body text")
    monkeypatch.setattr(
        paste_link_module.trafilatura, "extract_metadata", lambda html, default_url=None: None
    )

    source = extract_source("https://example.com/no-metadata")
    assert source.title == "https://example.com/no-metadata"
    assert source.author is None


def _sample_source() -> Source:
    return Source(
        title="A New Law Affecting Women",
        author="Jane Reporter",
        url="https://example.com/article",
        excerpt="The extracted article body.",
        retrieved_at=datetime.now(timezone.utc),
    )


def test_build_paste_link_brief_pins_source_and_requires_citation():
    source = _sample_source()
    llm = _FakeLLM(json.dumps({"visual_subject": "a stack of unopened certified mail on a doormat"}))
    result = build_paste_link_brief(source, WGS_BRAND_KIT, [], llm)
    assert isinstance(result, BriefResult)
    assert result.brief.requires_citation is True
    assert result.brief.sources == [source]
    assert result.brief.topic_name == source.title
    assert result.brief.slide_count == 3  # carousel default


def test_build_paste_link_brief_uses_llm_visual_subject_for_hero_image_prompt():
    source = _sample_source()
    llm = _FakeLLM(json.dumps({"visual_subject": "a hand hesitating over a 'sign here' tab"}))
    result = build_paste_link_brief(source, WGS_BRAND_KIT, [], llm)
    assert result.brief.hero_image_prompt == (
        "Abstract, editorial, textural image of a hand hesitating over a 'sign here' "
        "tab, no literal faces or text, wisdom mood."
    )
    # the LLM call was grounded in the actual article, not just the bare title
    assert "Excerpt" in llm.prompts[0]


def test_build_paste_link_brief_falls_back_to_title_when_llm_response_malformed():
    source = Source(
        title="A New Law Affecting Women's Rights at Work",
        author=None,
        url="https://example.com/article",
        excerpt="excerpt",
        retrieved_at=datetime.now(timezone.utc),
    )
    llm = _FakeLLM("not json at all")
    result = build_paste_link_brief(source, WGS_BRAND_KIT, [], llm)
    assert result.brief.hero_image_prompt == (
        "Abstract, editorial, textural image of A New Law Affecting Women's Rights "
        "at Work, no literal faces or text, wisdom mood."
    )


def test_build_paste_link_brief_resolves_direct_register_for_stat_research():
    llm = _FakeLLM(json.dumps({"visual_subject": "a subject"}))
    result = build_paste_link_brief(_sample_source(), WGS_BRAND_KIT, [], llm)
    assert result.brief.brand_voice_samples == WGS_BRAND_KIT.voice_samples.direct


def test_build_paste_link_brief_single_image_slide_count():
    llm = _FakeLLM(json.dumps({"visual_subject": "a subject"}))
    result = build_paste_link_brief(
        _sample_source(), WGS_BRAND_KIT, [], llm, format=Format.SINGLE_IMAGE
    )
    assert result.brief.slide_count == 1


def test_build_paste_link_brief_masthead_counts_category():
    memory = [
        MemoryRecord(
            id="m1",
            date=date(2026, 1, 1),
            topic_id="x",
            category="Society",
            angle="a",
            approach=Approach.STAT_RESEARCH,
            format=Format.CAROUSEL,
            mood="wisdom",
            hook="h",
            fingerprint="fp",
            status="exported",
        )
    ]
    llm = _FakeLLM(json.dumps({"visual_subject": "a subject"}))
    result = build_paste_link_brief(_sample_source(), WGS_BRAND_KIT, memory, llm)
    assert result.masthead == "WGS — SOCIETY NO. 02"
